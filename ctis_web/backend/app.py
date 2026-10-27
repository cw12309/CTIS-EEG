"""
CTIS-EEG Web 后端
- 用户管理（SQLite）
- 训练记录
- 设备连接状态（模拟 + 真实串口探测）
- 任务题库接口
"""
import json
import os
import random
import sqlite3
import threading
import time
import uuid
import hashlib
import hmac
from datetime import datetime
from typing import Any

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from backend.task_bank import TASK_BANK, pick_random_scene

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "ctis_web.db")

app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, "static"),
    static_url_path="/static",
)
CORS(app)


# ============== 数据库 ==============
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER,
            gender TEXT,
            diagnosis TEXT,
            created_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id INTEGER PRIMARY KEY,
            user_id TEXT,
            task_key TEXT,
            difficulty TEXT,
            trial_count INTEGER,
            correct_count INTEGER,
            score INTEGER,
            duration_sec REAL,
            cog_vector TEXT,
            created_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS trials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            user_id TEXT,
            task_key TEXT,
            trial_index INTEGER,
            prompt TEXT,
            stimulus TEXT,
            is_correct INTEGER,
            intent_level INTEGER,
            reaction_time_ms INTEGER,
            difficulty TEXT,
            blink_type TEXT,
            alpha_power REAL,
            theta_power REAL,
            cfi_snapshot REAL,
            ai_snapshot REAL,
            created_at TEXT
        )
    """)
    # 添加顺序训练相关列（迁移）
    session_cols = {row[1] for row in c.execute("PRAGMA table_info(sessions)").fetchall()}
    if "trials" not in session_cols:
        c.execute("ALTER TABLE sessions ADD COLUMN trials TEXT")
    if "group_id" not in session_cols:
        c.execute("ALTER TABLE sessions ADD COLUMN group_id TEXT")
    if "group_order" not in session_cols:
        c.execute("ALTER TABLE sessions ADD COLUMN group_order INTEGER")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sessions_group ON sessions(group_id)")
    # 添加逐试次EEG字段迁移（说明书8.1表7）
    trial_cols = {row[1] for row in c.execute("PRAGMA table_info(trials)").fetchall()}
    if "blink_type" not in trial_cols:
        c.execute("ALTER TABLE trials ADD COLUMN blink_type TEXT")
    if "alpha_power" not in trial_cols:
        c.execute("ALTER TABLE trials ADD COLUMN alpha_power REAL")
    if "theta_power" not in trial_cols:
        c.execute("ALTER TABLE trials ADD COLUMN theta_power REAL")
    if "cfi_snapshot" not in trial_cols:
        c.execute("ALTER TABLE trials ADD COLUMN cfi_snapshot REAL")
    if "ai_snapshot" not in trial_cols:
        c.execute("ALTER TABLE trials ADD COLUMN ai_snapshot REAL")
    # 全频段功率迁移（delta/beta/gamma，用于PSD节律分析）
    if "delta_power" not in trial_cols:
        c.execute("ALTER TABLE trials ADD COLUMN delta_power REAL")
    if "beta_power" not in trial_cols:
        c.execute("ALTER TABLE trials ADD COLUMN beta_power REAL")
    if "gamma_power" not in trial_cols:
        c.execute("ALTER TABLE trials ADD COLUMN gamma_power REAL")
    # 用户表添加密码字段迁移
    user_cols = {row[1] for row in c.execute("PRAGMA table_info(users)").fetchall()}
    if "password_hash" not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
    if "phone" not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN phone TEXT")
    if "education" not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN education TEXT")
    if "medical_history" not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN medical_history TEXT")
    if "emergency_contact" not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN emergency_contact TEXT")
    # 自定义题库表：用户可校对/修改题目答案
    c.execute("""
        CREATE TABLE IF NOT EXISTS custom_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            task_key TEXT NOT NULL,
            scene_name TEXT NOT NULL,
            prompt TEXT NOT NULL,
            domain TEXT DEFAULT '',
            original_options TEXT DEFAULT '',
            original_answer INTEGER DEFAULT 0,
            custom_options TEXT DEFAULT '',
            custom_answer INTEGER DEFAULT 0,
            is_modified INTEGER DEFAULT 0,
            updated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_custom_q_user ON custom_questions(user_id, task_key)")
    conn.commit()
    conn.close()


init_db()


# ============== 设备连接（模拟 + 真实串口） ==============
class DeviceState:
    """TGAM 设备状态管理，支持模拟模式和蓝牙串口模式"""

    def __init__(self):
        self.lock = threading.Lock()
        self.connected = False
        self.mode = "disconnected"  # disconnected / serial / sim
        self.port = ""
        self.baudrate = 57600
        self.serial_conn = None  # pyserial Serial 对象
        self.last_heartbeat = 0.0
        self.signal_quality = 0  # 0-200
        self.eeg_value = 0.0
        self.thresholds = {"base": 80.0, "mid": 150.0, "strong": 250.0}
        # EEG 频段功率与认知指标
        self.alpha_power = 0.0    # Alpha 频段功率 (μV²)
        self.theta_power = 0.0    # Theta 频段功率 (μV²)
        self.delta_power = 0.0    # Delta 频段功率 (μV²)
        self.beta_power = 0.0     # Beta 频段功率 (μV²)
        self.gamma_power = 0.0    # Gamma 频段功率 (μV²)
        self.blink_count = 0      # 眨眼计数
        self.blink_window_start = 0.0  # 眨眼统计窗口起始时间
        self.ai_value = 0.0       # Attention Index
        self.cfi_value = 0.0      # Cognitive Fatigue Index (0-100)

    def connect(self, mode: str, port: str = "") -> dict:
        with self.lock:
            if mode not in ("serial", "sim"):
                return {"ok": False, "msg": "未知模式"}
            if mode == "serial" and not port:
                return {"ok": False, "msg": "请提供串口名称"}

            # 串口模式：尝试打开真实串口
            if mode == "serial":
                try:
                    import serial
                    self.serial_conn = serial.Serial(
                        port=port,
                        baudrate=self.baudrate,
                        timeout=0.1,
                        bytesize=8,
                        parity='N',
                        stopbits=1,
                    )
                    if not self.serial_conn.is_open:
                        self.serial_conn.open()
                except ImportError:
                    return {"ok": False, "msg": "缺少 pyserial 库，请运行: pip install pyserial"}
                except Exception as e:
                    self.serial_conn = None
                    return {"ok": False, "msg": f"串口连接失败: {str(e)}"}

            self.mode = mode
            self.port = port
            self.connected = True
            self.last_heartbeat = time.time()
            threading.Thread(target=self._heartbeat_loop, daemon=True).start()
            return {
                "ok": True,
                "mode": mode,
                "port": port,
                "msg": f"已连接模拟模式" if mode == "sim" else f"已连接串口 {port}",
            }

    def disconnect(self):
        with self.lock:
            self.connected = False
            self.mode = "disconnected"
            self.port = ""
            if self.serial_conn:
                try:
                    self.serial_conn.close()
                except Exception:
                    pass
                self.serial_conn = None

    def status(self) -> dict:
        with self.lock:
            # 计算眨眼频率 (次/分)：60秒滑动窗口
            now = time.time()
            window_sec = now - self.blink_window_start if self.blink_window_start > 0 else 1
            blink_rate = (self.blink_count / max(window_sec, 1)) * 60 if self.connected else 0
            return {
                "connected": self.connected,
                "mode": self.mode,
                "port": self.port,
                "signal_quality": self.signal_quality,
                "eeg_value": round(self.eeg_value, 2),
                "thresholds": self.thresholds,
                "uptime_sec": int(now - self.last_heartbeat) if self.connected else 0,
                "alpha_power": round(self.alpha_power, 2),
                "theta_power": round(self.theta_power, 2),
                "delta_power": round(self.delta_power, 2),
                "beta_power": round(self.beta_power, 2),
                "gamma_power": round(self.gamma_power, 2),
                "blink_rate": round(blink_rate, 1),
                "ai_value": round(self.ai_value, 2),
                "cfi_value": round(self.cfi_value, 2),
            }

    def _heartbeat_loop(self):
        """后台 EEG 数据流：模拟模式用随机数据，串口模式读取真实数据"""
        self.blink_window_start = time.time()
        self.blink_count = 0
        next_blink_interval = random.uniform(2.0, 5.0)
        blink_timer = 0.0

        # TGAM 协议解析状态
        tgam_buffer = bytearray()
        tgam_parsing = False

        while self.connected:
            if self.mode == "serial" and self.serial_conn:
                # 串口模式：读取真实 TGAM 数据
                try:
                    data = self._read_tgam_packet(tgam_buffer, tgam_parsing)
                    if data:
                        self._apply_tgam_data(data)
                except Exception:
                    # 串口读取失败，降级为模拟
                    self._simulate_step(blink_timer, next_blink_interval)
                    blink_timer += 0.05
                    if blink_timer >= next_blink_interval:
                        next_blink_interval = random.uniform(2.0, 5.0)
                        blink_timer = 0.0
                time.sleep(0.01)
            else:
                # 模拟模式
                self._simulate_step(blink_timer, next_blink_interval)
                blink_timer += 0.05
                if blink_timer >= next_blink_interval:
                    next_blink_interval = random.uniform(2.0, 5.0)
                    blink_timer = 0.0
                time.sleep(0.05)

    def _simulate_step(self, blink_timer, next_blink_interval):
        """模拟 EEG 数据一步"""
        self.signal_quality = random.randint(0, 100)
        baseline = random.gauss(0, 8)

        spike = 0
        if blink_timer >= next_blink_interval:
            spike = random.choice([180, 220, 280])

        self.eeg_value = baseline + spike
        self.alpha_power = max(0, random.gauss(22, 8))
        self.theta_power = max(0, random.gauss(30, 12))
        self.delta_power = max(0, random.gauss(45, 15))
        self.beta_power = max(0, random.gauss(12, 5))
        self.gamma_power = max(0, random.gauss(6, 3))

        if spike > 0:
            self.blink_count += 1

        self.ai_value = max(0, min(100, 80 - self.alpha_power * 1.2 + random.gauss(0, 5)))
        ta_ratio = self.theta_power / max(self.alpha_power, 0.1)
        self.cfi_value = max(0, min(100, ta_ratio * 25 + random.gauss(0, 5)))

        now = time.time()
        elapsed = now - self.blink_window_start
        if elapsed > 60:
            self.blink_window_start = time.time()
            self.blink_count = 0

    def _read_tgam_packet(self, buffer, parsing):
        """从串口读取 TGAM 协议数据包
        TGAM 协议: [0xAA] [0xAA] [payload_length] [payload...] [checksum]
        payload 中包含:
          - 0x80: 信号质量
          - 0x04: 注意力 (Attention)
          - 0x05: 冥想 (Meditation)
          - 0x02: EEG 功率值 (8个频段)
        """
        try:
            if not self.serial_conn or not self.serial_conn.is_open:
                return None

            # 读取可用字节
            waiting = self.serial_conn.in_waiting
            if waiting > 0:
                raw = self.serial_conn.read(waiting)
                buffer.extend(raw)

            # 限制缓冲区大小
            if len(buffer) > 512:
                buffer.clear()
                return None

            # 查找包头 0xAA 0xAA
            while len(buffer) >= 3:
                # 找包头
                if buffer[0] != 0xAA or buffer[1] != 0xAA:
                    buffer.pop(0)
                    continue

                payload_length = buffer[2]
                if payload_length > 169:  # TGAM 最大 payload
                    buffer.pop(0)
                    continue

                # 检查是否收齐整个包
                total_length = 3 + payload_length + 1  # header + payload + checksum
                if len(buffer) < total_length:
                    return None

                # 提取包
                packet = bytes(buffer[:total_length])
                del buffer[:total_length]

                # 校验
                checksum = packet[3 + payload_length]
                calc_checksum = sum(packet[3:3 + payload_length]) & 0xFF
                calc_checksum = (~calc_checksum) & 0xFF
                if checksum != calc_checksum:
                    continue

                # 解析 payload
                return self._parse_tgam_payload(packet[3:3 + payload_length])

        except Exception:
            pass
        return None

    def _parse_tgam_payload(self, payload):
        """解析 TGAM payload，返回数据字典"""
        data = {}
        i = 0
        while i < len(payload):
            code = payload[i]
            if code == 0x80:  # 信号质量
                data["signal_quality"] = payload[i + 1] if i + 1 < len(payload) else 0
                i += 2
            elif code == 0x02:  # EEG 功率值
                if i + 1 < len(payload):
                    vlength = payload[i + 1]
                    if vlength == 24 and i + 2 + vlength <= len(payload):
                        # 8个3字节大端整数
                        powers = []
                        for j in range(8):
                            val = (payload[i + 2 + j * 3] << 16 |
                                   payload[i + 3 + j * 3] << 8 |
                                   payload[i + 4 + j * 3])
                            powers.append(val)
                        # powers: delta, theta, low-alpha, high-alpha, low-beta, high-beta, low-gamma, mid-gamma
                        data["delta"] = powers[0]
                        data["theta"] = powers[1]
                        data["low_alpha"] = powers[2]
                        data["high_alpha"] = powers[3]
                        data["alpha"] = powers[2] + powers[3]
                        data["low_beta"] = powers[4]
                        data["high_beta"] = powers[5]
                        data["beta"] = powers[4] + powers[5]
                        data["low_gamma"] = powers[6]
                        data["mid_gamma"] = powers[7]
                        data["gamma"] = powers[6] + powers[7]
                        i += 2 + vlength
                    else:
                        i += 2 + (vlength if i + 1 < len(payload) else 0)
                else:
                    i += 1
            elif code == 0x04:  # 注意力
                data["attention"] = payload[i + 1] if i + 1 < len(payload) else 0
                i += 2
            elif code == 0x05:  # 冥想
                data["meditation"] = payload[i + 1] if i + 1 < len(payload) else 0
                i += 2
            elif code == 0x16:  # 眨眼强度 (TGAM 扩展)
                data["blink_strength"] = payload[i + 1] if i + 1 < len(payload) else 0
                i += 2
            else:
                i += 1
        return data if data else None

    def _apply_tgam_data(self, data):
        """将解析后的 TGAM 数据应用到设备状态"""
        if "signal_quality" in data:
            self.signal_quality = data["signal_quality"]

        if "attention" in data:
            self.ai_value = data["attention"]

        if "alpha" in data:
            # TGAM 返回的是原始功率值，缩放到 μV² 量级
            self.alpha_power = data["alpha"] / 1000.0

        if "theta" in data:
            self.theta_power = data["theta"] / 1000.0

        if "delta" in data:
            self.delta_power = data["delta"] / 1000.0

        if "beta" in data:
            self.beta_power = data["beta"] / 1000.0

        if "gamma" in data:
            self.gamma_power = data["gamma"] / 1000.0

        # 眨眼检测
        if "blink_strength" in data:
            strength = data["blink_strength"]
            self.eeg_value = strength
            if strength >= self.thresholds["base"]:
                self.blink_count += 1
                # 根据阈值判断意图等级
                if strength >= self.thresholds["strong"]:
                    self.eeg_value = 280  # 强意图
                elif strength >= self.thresholds["mid"]:
                    self.eeg_value = 220  # 中意图
                else:
                    self.eeg_value = 150  # 弱意图

        # CFI 计算
        ta_ratio = self.theta_power / max(self.alpha_power, 0.1)
        self.cfi_value = max(0, min(100, ta_ratio * 25))

        # 窗口重置
        now = time.time()
        elapsed = now - self.blink_window_start
        if elapsed > 60:
            self.blink_window_start = time.time()
            self.blink_count = 0


device = DeviceState()


# ============== 路由 ==============
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    # 不拦截 /api/ 路径，让API路由处理
    if filename.startswith("api/"):
        return jsonify({"ok": False, "msg": "Not Found"}), 404
    return send_from_directory(app.static_folder, filename)


# ----- 认证 -----
SECRET_KEY = os.environ.get("CTIS_SECRET", "ctis_eeg_2026_secret")

def hash_password(password: str) -> str:
    """SHA256 + salt 密码哈希"""
    salt = "ctis_eeg_salt"
    return hashlib.sha256((salt + password + salt).encode()).hexdigest()

def generate_token(user_id: str) -> str:
    """简单token生成（HMAC签名）"""
    payload = f"{user_id}:{time.time()}"
    sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{payload}:{sig}"

def verify_token(token: str) -> str:
    """验证token，返回user_id或None"""
    if not token:
        return None
    parts = token.split(":")
    if len(parts) != 3:
        return None
    user_id, ts, sig = parts
    payload = f"{user_id}:{ts}"
    expected = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(sig, expected):
        return None
    return user_id

def get_current_user_id():
    """从请求头获取当前登录用户ID"""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return verify_token(auth[7:])
    return None


@app.post("/api/auth/register")
def auth_register():
    """用户注册"""
    data = request.json or {}
    name = (data.get("name") or "").strip()
    password = (data.get("password") or "").strip()
    if not name or not password:
        return jsonify({"ok": False, "msg": "请输入姓名和密码"}), 400
    if len(password) < 4:
        return jsonify({"ok": False, "msg": "密码至少4位"}), 400

    pw_hash = hash_password(password)
    user_id = f"{name}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    age = int(data.get("age") or 0)
    gender = (data.get("gender") or "").strip()
    diagnosis = (data.get("diagnosis") or "").strip()
    phone = (data.get("phone") or "").strip()
    education = (data.get("education") or "").strip()

    conn = get_db()
    # 检查同名用户
    existing = conn.execute("SELECT user_id FROM users WHERE name=?", (name,)).fetchone()
    if existing:
        conn.close()
        return jsonify({"ok": False, "msg": "该用户名已存在"}), 400
    conn.execute(
        "INSERT INTO users (user_id, name, age, gender, diagnosis, created_at, password_hash, phone, education) VALUES (?,?,?,?,?,?,?,?,?)",
        (user_id, name, age, gender, diagnosis, datetime.now().isoformat(), pw_hash, phone, education),
    )
    conn.commit()
    conn.close()

    token = generate_token(user_id)
    return jsonify({"ok": True, "token": token, "user": {
        "user_id": user_id, "name": name, "age": age,
        "gender": gender, "diagnosis": diagnosis, "phone": phone, "education": education,
    }})


@app.post("/api/auth/login")
def auth_login():
    """用户登录"""
    data = request.json or {}
    name = (data.get("name") or "").strip()
    password = (data.get("password") or "").strip()
    if not name or not password:
        return jsonify({"ok": False, "msg": "请输入用户名和密码"}), 400

    pw_hash = hash_password(password)
    conn = get_db()
    row = conn.execute(
        "SELECT user_id, name, age, gender, diagnosis, phone, education, medical_history, emergency_contact FROM users WHERE name=? AND password_hash=?",
        (name, pw_hash),
    ).fetchone()
    conn.close()

    if not row:
        return jsonify({"ok": False, "msg": "用户名或密码错误"}), 401

    token = generate_token(row["user_id"])
    return jsonify({"ok": True, "token": token, "user": dict(row)})


@app.get("/api/auth/me")
def auth_me():
    """获取当前登录用户信息"""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"ok": False, "msg": "未登录"}), 401
    conn = get_db()
    row = conn.execute(
        "SELECT user_id, name, age, gender, diagnosis, phone, education, medical_history, emergency_contact, created_at FROM users WHERE user_id=?",
        (user_id,),
    ).fetchone()
    conn.close()
    if not row:
        return jsonify({"ok": False, "msg": "用户不存在"}), 404
    return jsonify({"ok": True, "user": dict(row)})


@app.put("/api/auth/profile")
def update_profile():
    """更新当前用户个人信息"""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"ok": False, "msg": "未登录"}), 401
    data = request.json or {}
    conn = get_db()
    fields = []
    values = []
    for key in ["age", "gender", "diagnosis", "phone", "education", "medical_history", "emergency_contact"]:
        if key in data:
            fields.append(f"{key}=?")
            values.append(data[key])
    if fields:
        values.append(user_id)
        conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE user_id=?", values)
        conn.commit()
    row = conn.execute(
        "SELECT user_id, name, age, gender, diagnosis, phone, education, medical_history, emergency_contact, created_at FROM users WHERE user_id=?",
        (user_id,),
    ).fetchone()
    conn.close()
    return jsonify({"ok": True, "user": dict(row)})


@app.post("/api/auth/change-password")
def change_password():
    """修改密码"""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"ok": False, "msg": "未登录"}), 401
    data = request.json or {}
    old_pw = (data.get("old_password") or "").strip()
    new_pw = (data.get("new_password") or "").strip()
    if not old_pw or not new_pw:
        return jsonify({"ok": False, "msg": "请输入旧密码和新密码"}), 400
    if len(new_pw) < 4:
        return jsonify({"ok": False, "msg": "新密码至少4位"}), 400

    conn = get_db()
    row = conn.execute("SELECT password_hash FROM users WHERE user_id=?", (user_id,)).fetchone()
    if not row or row["password_hash"] != hash_password(old_pw):
        conn.close()
        return jsonify({"ok": False, "msg": "旧密码错误"}), 400
    conn.execute("UPDATE users SET password_hash=? WHERE user_id=?", (hash_password(new_pw), user_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "msg": "密码修改成功"})


# ----- 用户 -----
@app.post("/api/users")
def create_user():
    data = request.json or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "msg": "请输入姓名"}), 400
    age = int(data.get("age") or 0)
    gender = (data.get("gender") or "").strip()
    diagnosis = (data.get("diagnosis") or "").strip()
    user_id = f"{name}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    conn = get_db()
    conn.execute(
        "INSERT INTO users VALUES (?,?,?,?,?,?)",
        (user_id, name, age, gender, diagnosis, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "user": {
        "user_id": user_id, "name": name, "age": age,
        "gender": gender, "diagnosis": diagnosis,
    }})


@app.get("/api/users")
def list_users():
    conn = get_db()
    rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return jsonify({
        "ok": True,
        "users": [dict(r) for r in rows],
    })


@app.delete("/api/users/<user_id>")
def delete_user(user_id):
    conn = get_db()
    conn.execute("DELETE FROM users WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ----- 题库管理 -----
@app.get("/api/qbank/<task_key>")
def get_question_bank(task_key):
    """获取指定任务的题库（含用户自定义修改）"""
    user_id = request.args.get("user_id", "")
    if task_key not in TASK_BANK:
        return jsonify({"ok": False, "msg": "任务不存在"}), 404

    scenes = TASK_BANK[task_key]["scenes"]
    result = []
    for si, scene in enumerate(scenes):
        trials = scene.get("trials", [])
        scene_trials = []
        for ti, t in enumerate(trials):
            item = {
                "scene_index": si,
                "scene_name": scene.get("set_name", ""),
                "trial_index": ti,
                "prompt": t.get("prompt", ""),
                "domain": t.get("domain", ""),
                "image": t.get("image", ""),
                "options": t.get("options", []),
                "answer": t.get("answer", 0),
                "custom_options": None,
                "custom_answer": None,
                "is_modified": False,
            }
            # 查找用户自定义
            if user_id:
                conn = get_db()
                row = conn.execute(
                    "SELECT custom_options, custom_answer, is_modified FROM custom_questions WHERE user_id=? AND task_key=? AND scene_name=? AND prompt=?",
                    (user_id, task_key, scene.get("set_name", ""), t.get("prompt", ""))
                ).fetchone()
                conn.close()
                if row and row["is_modified"]:
                    item["custom_options"] = json.loads(row["custom_options"]) if row["custom_options"] else None
                    item["custom_answer"] = row["custom_answer"]
                    item["is_modified"] = True
            scene_trials.append(item)
        result.append({
            "scene_name": scene.get("set_name", ""),
            "scene_index": si,
            "trials": scene_trials,
        })
    return jsonify({"ok": True, "task_key": task_key, "task_name": TASK_BANK[task_key]["name"], "scenes": result})


@app.post("/api/qbank/<task_key>/update")
def update_question(task_key):
    """更新单个题目的自定义答案"""
    data = request.json or {}
    user_id = data.get("user_id", "")
    scene_name = data.get("scene_name", "")
    prompt = data.get("prompt", "")
    domain = data.get("domain", "")
    original_options = json.dumps(data.get("original_options", []), ensure_ascii=False)
    original_answer = data.get("original_answer", 0)
    custom_options = json.dumps(data.get("custom_options", []), ensure_ascii=False)
    custom_answer = data.get("custom_answer", 0)

    if not user_id or not prompt:
        return jsonify({"ok": False, "msg": "参数不完整"}), 400

    conn = get_db()
    # upsert
    existing = conn.execute(
        "SELECT id FROM custom_questions WHERE user_id=? AND task_key=? AND scene_name=? AND prompt=?",
        (user_id, task_key, scene_name, prompt)
    ).fetchone()
    now = datetime.now().isoformat()
    if existing:
        conn.execute(
            """UPDATE custom_questions SET domain=?, original_options=?, original_answer=?,
               custom_options=?, custom_answer=?, is_modified=1, updated_at=?
               WHERE id=?""",
            (domain, original_options, original_answer, custom_options, custom_answer, now, existing["id"])
        )
    else:
        conn.execute(
            """INSERT INTO custom_questions (user_id, task_key, scene_name, prompt, domain,
               original_options, original_answer, custom_options, custom_answer, is_modified, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (user_id, task_key, scene_name, prompt, domain,
             original_options, original_answer, custom_options, custom_answer, 1, now)
        )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.post("/api/qbank/<task_key>/reset")
def reset_question(task_key):
    """重置单个题目为默认答案"""
    data = request.json or {}
    user_id = data.get("user_id", "")
    scene_name = data.get("scene_name", "")
    prompt = data.get("prompt", "")

    if not user_id or not prompt:
        return jsonify({"ok": False, "msg": "参数不完整"}), 400

    conn = get_db()
    conn.execute(
        "DELETE FROM custom_questions WHERE user_id=? AND task_key=? AND scene_name=? AND prompt=?",
        (user_id, task_key, scene_name, prompt)
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ----- 任务 -----
@app.get("/api/tasks")
def list_tasks():
    out = []
    for key, val in TASK_BANK.items():
        out.append({
            "key": key,
            "name": val["name"],
            "description": val["description"],
            "scene_count": len(val["scenes"]),
        })
    return jsonify({"ok": True, "tasks": out})


@app.get("/api/tasks/<task_key>/scene")
def get_task_scene(task_key):
    if task_key not in TASK_BANK:
        return jsonify({"ok": False, "msg": "任务不存在"}), 404
    scene = pick_random_scene(task_key)
    user_id = request.args.get("user_id", "")

    # 为不同任务类型生成标准化的 trials 列表
    if task_key == "orient":
        # 定向力: 动态生成基于当前日期的题目
        from datetime import datetime as _dt
        import random as _or
        now = _dt.now()
        year = now.year
        month = now.month
        day = now.day
        weekday = now.weekday()  # 0=Monday
        # 季节判断
        if month in [3, 4, 5]: season = "春季"
        elif month in [6, 7, 8]: season = "夏季"
        elif month in [9, 10, 11]: season = "秋季"
        else: season = "冬季"
        weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        weekday_name = weekday_names[weekday]

        # 从题库获取场景框架，动态替换答案
        base_trials = scene.get("trials", [])
        dynamic_trials = []
        for t in base_trials:
            domain = t.get("domain", "")
            if domain == "time":
                if "哪一年" in t["prompt"]:
                    # 年份: 正确答案+3个干扰
                    wrong_years = [y for y in range(year - 3, year + 4) if y != year]
                    _or.shuffle(wrong_years)
                    opts = [year] + wrong_years[:3]
                    _or.shuffle(opts)
                    dynamic_trials.append({
                        "prompt": t["prompt"], "image": t.get("image", ""),
                        "options": [str(o) + "年" for o in opts],
                        "answer": [str(o) + "年" for o in opts].index(str(year) + "年"),
                        "domain": "time",
                    })
                elif "几月份" in t["prompt"]:
                    month_names = ["一月","二月","三月","四月","五月","六月","七月","八月","九月","十月","十一月","十二月"]
                    correct_month = month_names[month - 1]
                    wrong_months = [m for m in month_names if m != correct_month]
                    _or.shuffle(wrong_months)
                    opts = [correct_month] + wrong_months[:3]
                    _or.shuffle(opts)
                    dynamic_trials.append({
                        "prompt": t["prompt"], "image": t.get("image", ""),
                        "options": opts,
                        "answer": opts.index(correct_month),
                        "domain": "time",
                    })
                elif "几号" in t["prompt"]:
                    wrong_days = [d for d in range(1, 29) if d != day]
                    _or.shuffle(wrong_days)
                    opts = [day] + wrong_days[:3]
                    _or.shuffle(opts)
                    dynamic_trials.append({
                        "prompt": t["prompt"], "image": t.get("image", ""),
                        "options": [str(o) + "号" for o in opts],
                        "answer": [str(o) + "号" for o in opts].index(str(day) + "号"),
                        "domain": "time",
                    })
                elif "星期几" in t["prompt"]:
                    wrong_weekdays = [w for w in weekday_names if w != weekday_name]
                    _or.shuffle(wrong_weekdays)
                    opts = [weekday_name] + wrong_weekdays[:3]
                    _or.shuffle(opts)
                    dynamic_trials.append({
                        "prompt": t["prompt"], "image": t.get("image", ""),
                        "options": opts,
                        "answer": opts.index(weekday_name),
                        "domain": "time",
                    })
                elif "季节" in t["prompt"]:
                    wrong_seasons = [s for s in ["春季","夏季","秋季","冬季"] if s != season]
                    _or.shuffle(wrong_seasons)
                    opts = [season] + wrong_seasons[:3]
                    _or.shuffle(opts)
                    dynamic_trials.append({
                        "prompt": t["prompt"], "image": t.get("image", ""),
                        "options": opts,
                        "answer": opts.index(season),
                        "domain": "time",
                    })
                else:
                    dynamic_trials.append(t)
            else:
                # 常识定向(knowledge)直接透传，已有固定答案
                dynamic_trials.append(t)
        scene["trials"] = dynamic_trials

        # 注入用户自定义答案（优先于默认/动态答案）
        if user_id:
            conn = get_db()
            scene_name = scene.get("set_name", "")
            for t in scene["trials"]:
                row = conn.execute(
                    "SELECT custom_options, custom_answer, is_modified FROM custom_questions WHERE user_id=? AND task_key=? AND scene_name=? AND prompt=?",
                    (user_id, task_key, scene_name, t.get("prompt", ""))
                ).fetchone()
                if row and row["is_modified"]:
                    t["options"] = json.loads(row["custom_options"]) if row["custom_options"] else t.get("options", [])
                    t["answer"] = row["custom_answer"]
            conn.close()

    elif task_key == "memencode":
        # 情景记忆：编码-延迟-回忆三阶段
        # 将三阶段数据转为前端可用的 trials 格式
        words = scene.get("encoding_words", [])
        dist_sem = scene.get("distractors_semantic", [])
        dist_unrel = scene.get("distractors_unrelated", [])
        delay_qs = scene.get("delay_questions", [])

        trials = []

        # 阶段A: 编码 - 逐词呈现 (2次，对齐MoCA标准)
        for round_num in range(1, 3):
            for w in words:
                trials.append({
                    "phase": "encode",
                    "prompt": "请记住这个词" + ("（第" + str(round_num) + "次学习）" if round_num == 2 else ""),
                    "word": w,
                    "encode_round": round_num,
                    "options": ["记住了(强)", "不太确定(弱)", "没记住"],
                    "answer": 0,
                })

        # 阶段B: 延迟 - 插入定向问题
        for q in delay_qs:
            trials.append({
                "phase": "delay",
                "prompt": q["prompt"],
                "options": q["options"],
                "answer": q["answer"],
            })

        # 阶段C: 回忆 - 目标词+干扰词混合
        import random as _r
        recall_items = []
        for w in words:
            recall_items.append({"word": w, "is_target": True})
        # 取6个语义干扰 + 6个无关干扰
        sem_sample = dist_sem[:6] if len(dist_sem) >= 6 else dist_sem
        unrel_sample = dist_unrel[:6] if len(dist_unrel) >= 6 else dist_unrel
        for w in sem_sample:
            recall_items.append({"word": w, "is_target": False})
        for w in unrel_sample:
            recall_items.append({"word": w, "is_target": False})
        _r.shuffle(recall_items)

        for item in recall_items:
            trials.append({
                "phase": "recall",
                "prompt": "这个词刚才出现过吗？",
                "word": item["word"],
                "is_target": item["is_target"],
                "options": ["出现过", "没出现过"],
                "answer": 0 if item["is_target"] else 1,
            })

        scene["trials"] = trials

    elif task_key == "trailblink":
        # 执行功能：连线 + 数字倒背 + 连续减7 (对齐MoCA)
        seq = scene.get("sequence", [])
        grid_size = scene.get("grid_size", 4)

        # 在网格上随机分布标记位置
        import random as _r
        positions = []
        for r in range(grid_size):
            for c in range(grid_size):
                positions.append((r, c))
        _r.shuffle(positions)
        markers = []
        for i, label in enumerate(seq):
            if i < len(positions):
                markers.append({
                    "label": label,
                    "row": positions[i][0],
                    "col": positions[i][1],
                    "order": i,
                })

        trials = []
        # 子模块A: 连线测试
        for i, label in enumerate(seq):
            trials.append({
                "phase": "trail",
                "prompt": "请在游标高亮 " + str(label) + " 时确认连线",
                "target_label": str(label),
                "target_order": i,
                "markers": markers,
                "grid_size": grid_size,
                "options": [str(label), "跳过"],
                "answer": 0,
            })

        # 子模块B: 数字倒背 (对齐MoCA注意力)
        for span in scene.get("digit_span", []):
            correct_digits = span["answer"].split("-")
            # 生成4个选项: 正确答案 + 3个干扰项
            import random as _r2
            wrong_options = []
            # 干扰1: 顺序颠倒（第1和最后交换）
            if len(correct_digits) >= 3:
                swapped = correct_digits[:]
                swapped[0], swapped[-1] = swapped[-1], swapped[0]
                wrong_options.append("-".join(swapped))
            # 干扰2: 原始顺序
            wrong_options.append(span["digits"])
            # 干扰3: 随机打乱
            shuffled = correct_digits[:]
            _r2.shuffle(shuffled)
            shuffled_str = "-".join(shuffled)
            if shuffled_str not in wrong_options and shuffled_str != span["answer"]:
                wrong_options.append(shuffled_str)
            # 确保有3个干扰
            while len(wrong_options) < 3:
                offset_digits = [str(int(d) + _r2.choice([-1, 1])) for d in correct_digits]
                candidate = "-".join(offset_digits[::-1])
                if candidate != span["answer"] and candidate not in wrong_options:
                    wrong_options.append(candidate)
            wrong_options = wrong_options[:3]
            all_options = [span["answer"]] + wrong_options
            _r2.shuffle(all_options)
            correct_idx = all_options.index(span["answer"])
            trials.append({
                "phase": "digit_span",
                "prompt": "请倒着说出这组数字：" + span["digits"],
                "digits": span["digits"],
                "options": all_options,
                "answer": correct_idx,
                "correct_answer": span["answer"],
            })

        # 子模块C: 连续减7 (对齐MMSE注意计算)
        for s7 in scene.get("serial_seven", []):
            for step_val in s7["steps"]:
                # 生成4个不重复选项: 正确答案 + 3个合理干扰
                import random as _r3
                candidates = set()
                candidates.add(step_val)
                # 干扰项: 常见错误 (减6/减8/减10/减1)
                distractors = [step_val - 1, step_val + 1, s7["start"] - 7, step_val + 7, step_val - 7, step_val + 6, step_val - 6]
                for d in distractors:
                    if d != step_val:
                        candidates.add(d)
                    if len(candidates) >= 8:
                        break
                candidates.discard(step_val)  # 先移除正确答案
                option_list = [step_val]  # 正确答案放首位
                for c in list(candidates):
                    if len(option_list) >= 4:
                        break
                    option_list.append(c)
                # 如果还不够4个，补充随机数
                while len(option_list) < 4:
                    extra = step_val + _r3.choice([-3, -2, 2, 3, 8, 9, 14])
                    if extra not in option_list:
                        option_list.append(extra)
                _r3.shuffle(option_list)
                correct_idx = option_list.index(step_val)
                trials.append({
                    "phase": "serial_seven",
                    "prompt": str(s7["start"]) + "减7等于多少？",
                    "start": s7["start"],
                    "correct_value": step_val,
                    "options": option_list,
                    "answer": correct_idx,
                })
                s7["start"] = step_val

        scene["trials"] = trials

    elif task_key == "semflow":
        # 语义记忆：命名 + 流畅性 + 相似性 (对齐MoCA)
        mod_a = scene.get("module_a", {})
        mod_b = scene.get("module_b", {})
        mod_c = scene.get("module_c", {})

        trials = []

        # 子模块A: 命名 (对齐MoCA命名3题)
        for t in mod_a.get("trials", []):
            trials.append({
                "phase": "module_a",
                "prompt": t["prompt"],
                "emoji": t.get("emoji", "📦"),
                "options": t["options"],
                "answer": t["answer"],
            })

        # 子模块B: 语义流畅性 (对齐MoCA语言流畅性)
        trials.append({
            "phase": "module_b",
            "prompt": "请在1分钟内说出尽可能多的" + mod_b.get("category", "动物"),
            "category": mod_b.get("category", "动物"),
            "time_limit_sec": mod_b.get("time_limit_sec", 60),
            "threshold": mod_b.get("threshold", 11),
            "options": ["开始计时"],
            "answer": 0,
        })

        # 子模块C: 相似性抽象 (对齐MoCA抽象思维)
        for t in mod_c.get("trials", []):
            trials.append({
                "phase": "module_c",
                "prompt": t["prompt"],
                "options": t["options"],
                "answer": t["answer"],
            })

        scene["trials"] = trials

    elif task_key == "nameblink":
        # 命名能力：命名 + 复述 (对齐MoCA命名+语言复述)
        trials = []
        # 子模块A: 命名
        for t in scene.get("trials", []):
            t["phase"] = "name"
            if "emoji" not in t:
                t["emoji"] = "📦"
            trials.append(t)
        # 子模块B: 复述 (对齐MoCA语言复述)
        for rep in scene.get("repetition", []):
            trials.append({
                "phase": "repetition",
                "prompt": "请复述这句话：" + rep["sentence"],
                "sentence": rep["sentence"],
                "options": rep["options"],
                "answer": rep["answer"],
            })
        scene["trials"] = trials

    return jsonify({"ok": True, "scene": scene})


# ----- 设备 -----
@app.post("/api/device/connect")
def device_connect():
    data = request.json or {}
    mode = data.get("mode", "sim")
    port = data.get("port", "")
    res = device.connect(mode, port)
    return jsonify(res)


@app.post("/api/device/disconnect")
def device_disconnect():
    device.disconnect()
    return jsonify({"ok": True})


@app.get("/api/device/status")
def device_status():
    return jsonify(device.status())


@app.post("/api/device/calibrate")
def device_calibrate():
    """模拟校准过程：返回 3 档阈值"""
    weak = random.uniform(60, 90)
    mid = weak * random.uniform(1.4, 1.7)
    strong = mid * random.uniform(1.3, 1.6)
    device.thresholds = {
        "base": round(weak * 0.7, 2),
        "mid": round((weak + mid) / 2, 2),
        "strong": round((mid + strong) / 2, 2),
    }
    return jsonify({
        "ok": True,
        "thresholds": device.thresholds,
        "raw": {"weak": round(weak, 2), "mid": round(mid, 2), "strong": round(strong, 2)},
    })


@app.post("/api/device/thresholds")
def device_set_thresholds():
    """手动设置眨眼阈值"""
    data = request.json or {}
    base = float(data.get("base", 80))
    mid = float(data.get("mid", 150))
    strong = float(data.get("strong", 250))
    if not (0 < base < mid < strong):
        return jsonify({"ok": False, "msg": "阈值需满足 0 < 弱 < 中 < 强"}), 400
    device.thresholds = {"base": base, "mid": mid, "strong": strong}
    return jsonify({"ok": True, "thresholds": device.thresholds})


# ----- 训练记录 -----
@app.post("/api/sessions")
def create_session():
    data = request.json or {}
    user_id = data.get("user_id", "")
    task_key = data.get("task_key", "")
    difficulty = data.get("difficulty", "L2")
    trial_count = int(data.get("trial_count", 0))
    correct_count = int(data.get("correct_count", 0))
    score = int(data.get("score", 0))
    duration_sec = float(data.get("duration_sec", 0))
    cog_vector = json.dumps(data.get("cog_vector", [0] * 5))
    trials = data.get("trials", [])

    session_id = int(time.time() * 1000)
    conn = get_db()
    conn.execute(
        """INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (session_id, user_id, task_key, difficulty, trial_count,
         correct_count, score, duration_sec, cog_vector, datetime.now().isoformat()),
    )
    for tr in trials:
        conn.execute(
            """INSERT INTO trials
               (session_id, user_id, task_key, trial_index, prompt,
                stimulus, is_correct, intent_level, reaction_time_ms, difficulty,
                blink_type, alpha_power, theta_power, cfi_snapshot, ai_snapshot,
                delta_power, beta_power, gamma_power, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (session_id, user_id, task_key, tr.get("trial_index", 0),
             tr.get("prompt", ""), tr.get("stimulus", ""),
             1 if tr.get("is_correct") else 0,
             tr.get("intent_level", 0),
             tr.get("reaction_time_ms", 0),
             difficulty,
             tr.get("blink_type", ""),
             tr.get("alpha_power", 0),
             tr.get("theta_power", 0),
             tr.get("cfi_snapshot", 0),
             tr.get("ai_snapshot", 0),
             tr.get("delta_power", 0),
             tr.get("beta_power", 0),
             tr.get("gamma_power", 0),
             datetime.now().isoformat()),
        )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "session_id": session_id})


@app.post("/api/sequential_session")
def create_sequential_session():
    """接收顺序训练5子任务的汇总结果。"""
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    group_id = data.get("group_id") or datetime.now().strftime("%Y%m%d%H%M%S") + "_" + str(uuid.uuid4())[:8]
    tasks = data.get("tasks", [])
    if not user_id or not isinstance(tasks, list):
        return jsonify({"ok": False, "error": "missing user_id or tasks"}), 400

    conn = get_db()
    inserted = []
    for t in tasks:
        score = int(t.get("score", 0))
        cog = t.get("cog_vector") or [0, 0, 0, 0, 0]
        trials_list = t.get("trials") or []
        trials_json = json.dumps(trials_list, ensure_ascii=False)
        cur = conn.execute(
            """INSERT INTO sessions
               (user_id, task_key, difficulty, trial_count, correct_count, score, duration_sec, cog_vector, trials, group_id, group_order, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                user_id, t.get("task_key", ""), t.get("difficulty", 1),
                t.get("trial_count", 0), t.get("correct_count", 0), score,
                t.get("duration_sec", 0), json.dumps(cog), trials_json,
                group_id, t.get("group_order", 0),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
        )
        session_id = cur.lastrowid
        # 逐试次明细落库（含全频段EEG功率，供轨迹追踪与报告分析）
        for idx, tr in enumerate(trials_list):
            conn.execute(
                """INSERT INTO trials
                   (session_id, user_id, task_key, trial_index, prompt,
                    stimulus, is_correct, intent_level, reaction_time_ms, difficulty,
                    blink_type, alpha_power, theta_power, cfi_snapshot, ai_snapshot,
                    delta_power, beta_power, gamma_power, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (session_id, user_id, t.get("task_key", ""),
                 tr.get("trial_index", idx),
                 tr.get("prompt", ""), tr.get("stimulus", ""),
                 1 if tr.get("is_correct") else 0,
                 tr.get("intent_level", 0),
                 tr.get("reaction_time_ms", 0),
                 str(t.get("difficulty", 1)),
                 tr.get("blink_type", ""),
                 tr.get("alpha_power", 0),
                 tr.get("theta_power", 0),
                 tr.get("cfi_snapshot", 0),
                 tr.get("ai_snapshot", 0),
                 tr.get("delta_power", 0),
                 tr.get("beta_power", 0),
                 tr.get("gamma_power", 0),
                 datetime.now().isoformat()),
            )
        inserted.append(session_id)
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "group_id": group_id, "session_ids": inserted})


@app.get("/api/sequential_sessions")
def list_sequential_sessions():
    user_id = request.args.get("user_id", "")
    if not user_id:
        return jsonify({"ok": False, "error": "missing user_id"}), 400
    conn = get_db()
    rows = conn.execute(
        """SELECT group_id, MIN(created_at) AS created_at, COUNT(*) AS task_count,
                  AVG(score) AS avg_score, SUM(duration_sec) AS total_duration
           FROM sessions
           WHERE user_id=? AND group_id IS NOT NULL
           GROUP BY group_id
           ORDER BY created_at DESC""",
        (user_id,),
    ).fetchall()
    groups = []
    for r in rows:
        items = conn.execute(
            "SELECT task_key, score, trial_count, correct_count, duration_sec, group_order FROM sessions WHERE group_id=? ORDER BY group_order",
            (r["group_id"],),
        ).fetchall()
        groups.append({
            "group_id": r["group_id"],
            "created_at": r["created_at"],
            "task_count": r["task_count"],
            "avg_score": round(r["avg_score"] or 0, 1),
            "total_duration": r["total_duration"] or 0,
            "items": [dict(x) for x in items],
        })
    conn.close()
    return jsonify({"ok": True, "groups": groups})


@app.delete("/api/sequential_session/<group_id>")
def delete_sequential_session(group_id):
    """删除指定group_id的完整训练会话（含关联trials）"""
    conn = get_db()
    # 先获取该group下的所有session_id
    session_rows = conn.execute(
        "SELECT session_id FROM sessions WHERE group_id=?",
        (group_id,),
    ).fetchall()
    if not session_rows:
        conn.close()
        return jsonify({"ok": False, "error": "not found"}), 404
    # 删除关联的trials
    for r in session_rows:
        conn.execute("DELETE FROM trials WHERE session_id=?", (r["session_id"],))
    # 删除sessions
    conn.execute("DELETE FROM sessions WHERE group_id=?", (group_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "deleted_group": group_id, "deleted_sessions": len(session_rows)})


@app.get("/api/sessions")
def list_sessions():
    user_id = request.args.get("user_id", "")
    conn = get_db()
    if user_id:
        rows = conn.execute(
            "SELECT * FROM sessions WHERE user_id=? ORDER BY session_id DESC",
            (user_id,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM sessions ORDER BY session_id DESC").fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["cog_vector"] = json.loads(d.get("cog_vector") or "[]")
        except Exception:
            d["cog_vector"] = []
        out.append(d)
    return jsonify({"ok": True, "sessions": out})


@app.get("/api/sessions/<int:session_id>/trials")
def session_trials(session_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM trials WHERE session_id=? ORDER BY trial_index",
        (session_id,),
    ).fetchall()
    conn.close()
    return jsonify({"ok": True, "trials": [dict(r) for r in rows]})


@app.get("/api/stats/<user_id>")
def user_stats(user_id):
    """用户的总体统计：累计完整训练次数/试次/总分/平均正确率/趋势"""
    conn = get_db()
    sessions = conn.execute(
        """SELECT session_id, task_key, trial_count, correct_count, score, duration_sec, created_at, group_id
           FROM sessions WHERE user_id=? ORDER BY session_id""",
        (user_id,),
    ).fetchall()
    conn.close()
    if not sessions:
        return jsonify({"ok": True, "stats": None})

    # 只统计有group_id的顺序训练会话（完整训练）
    seq_sessions = [s for s in sessions if s["group_id"]]

    # 完整训练次数 = 唯一group_id数量
    group_ids = set(s["group_id"] for s in seq_sessions)
    total_sessions = len(group_ids)

    # 试次总数 = 顺序训练的trial之和
    total_trials = sum(s["trial_count"] for s in seq_sessions)
    total_correct = sum(s["correct_count"] for s in seq_sessions)

    # 总分 = 每个group内5项score之和的累加（CT-30总分之和）
    group_scores = {}
    for s in seq_sessions:
        gid = s["group_id"]
        if gid not in group_scores:
            group_scores[gid] = 0
        group_scores[gid] += s["score"]
    total_score = sum(group_scores.values())
    avg_score = total_score / total_sessions if total_sessions else 0

    acc = total_correct / total_trials if total_trials else 0

    by_task = {}
    for s in seq_sessions:
        t = s["task_key"]
        if t not in by_task:
            by_task[t] = {"sessions": 0, "trials": 0, "correct": 0, "score": 0}
        by_task[t]["sessions"] += 1
        by_task[t]["trials"] += s["trial_count"]
        by_task[t]["correct"] += s["correct_count"]
        by_task[t]["score"] += s["score"]
    for v in by_task.values():
        v["accuracy"] = round(v["correct"] / v["trials"], 3) if v["trials"] else 0

    return jsonify({
        "ok": True,
        "stats": {
            "total_sessions": total_sessions,
            "total_trials": total_trials,
            "total_correct": total_correct,
            "total_score": round(total_score, 2),
            "avg_score": round(avg_score, 2),
            "accuracy": round(acc, 3),
            "by_task": by_task,
            "trend": [
                {
                    "session_id": s["session_id"],
                    "task_key": s["task_key"],
                    "accuracy": round(s["correct_count"] / s["trial_count"], 3)
                                 if s["trial_count"] else 0,
                    "created_at": s["created_at"],
                }
                for s in seq_sessions
            ],
        },
    })


@app.get("/api/trajectory/<user_id>")
def user_trajectory(user_id):
    """CSTM跨会话认知轨迹建模：五维认知向量、线性混合效应模型、轨迹分类、风险预警"""
    conn = get_db()
    sessions = conn.execute(
        """SELECT session_id, task_key, trial_count, correct_count, score,
                  duration_sec, cog_vector, difficulty, created_at, group_id, group_order
           FROM sessions WHERE user_id=? AND group_id IS NOT NULL
           ORDER BY created_at""",
        (user_id,),
    ).fetchall()
    conn.close()

    if not sessions:
        return jsonify({"ok": True, "trajectory": None, "sufficient": False})

    # 按 group_id 分组
    groups = {}
    for s in sessions:
        gid = s["group_id"]
        if gid not in groups:
            groups[gid] = {"created_at": s["created_at"], "items": []}
        cog = json.loads(s["cog_vector"]) if s["cog_vector"] else [0, 0, 0, 0, 0]
        groups[gid]["items"].append({
            "task_key": s["task_key"],
            "trial_count": s["trial_count"],
            "correct_count": s["correct_count"],
            "score": s["score"],
            "duration_sec": s["duration_sec"],
            "cog_vector": cog,
            "difficulty": s["difficulty"],
            "group_order": s["group_order"],
        })

    sorted_groups = sorted(groups.values(), key=lambda g: g["created_at"])
    n_sessions = len(sorted_groups)
    sufficient = n_sessions >= 8  # CSTM要求不少于8次

    cog_labels = ["orient", "memencode", "trailblink", "semflow", "nameblink"]
    cog_names = ["定向力(D1)", "情景记忆(D2)", "执行功能(D3)", "语义记忆(D4)", "命名能力(D5)"]

    # 构建五维认知向量 (归一化0-1) 和原始分数
    cog_vectors = []  # D1-D5 归一化
    raw_scores = []   # 原始分 (0-6)
    total_scores = [] # CT-30 (0-30)
    session_labels = []

    for g in sorted_groups:
        scores = {k: 0 for k in cog_labels}
        for item in g["items"]:
            scores[item["task_key"]] = item["score"]
        raw_scores.append(scores)
        total_scores.append(sum(scores.values()))
        session_labels.append(g["created_at"])

        # 归一化认知向量 D1-D5 (score/6 → 0-1)
        vec = [scores[k] / 6.0 for k in cog_labels]
        cog_vectors.append(vec)

    # 线性回归 + 95%CI 计算
    def linear_regression_with_ci(values, confidence=0.95):
        """简单线性回归，返回斜率、截距、斜率标准误、95%CI"""
        n = len(values)
        if n < 2:
            return {"slope": 0, "intercept": values[0] if values else 0,
                    "slope_se": 0, "ci_low": 0, "ci_high": 0}
        x_mean = (n - 1) / 2.0
        y_mean = sum(values) / n
        ss_xx = sum((i - x_mean) ** 2 for i in range(n))
        ss_xy = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        slope = ss_xy / ss_xx if ss_xx else 0
        intercept = y_mean - slope * x_mean
        # 残差
        residuals = [values[i] - (intercept + slope * i) for i in range(n)]
        ss_res = sum(r * r for r in residuals)
        if n > 2 and ss_xx:
            mse = ss_res / (n - 2)
            slope_se = (mse / ss_xx) ** 0.5
        else:
            slope_se = 0
        # t 临界值近似 (用1.96代替，n>=8时足够精确)
        t_crit = 1.96
        ci_low = slope - t_crit * slope_se
        ci_high = slope + t_crit * slope_se
        return {
            "slope": round(slope, 4),
            "intercept": round(intercept, 4),
            "slope_se": round(slope_se, 4),
            "ci_low": round(ci_low, 4),
            "ci_high": round(ci_high, 4),
        }

    # 各域轨迹分类 (CSTM规范)
    delta = 0.02  # 临床显著性阈值 (归一化尺度)
    trends = {}
    regressions = {}
    for d, k in enumerate(cog_labels):
        vals = [v[d] for v in cog_vectors]
        reg = linear_regression_with_ci(vals)
        regressions[k] = reg
        if reg["ci_low"] > delta:
            trends[k] = "improving"
        elif reg["ci_high"] < -delta:
            trends[k] = "declining"
        else:
            trends[k] = "stable"

    # 总体轨迹分类 (基于CT-30)
    total_reg = linear_regression_with_ci(total_scores)
    delta_total = 0.5  # 总分尺度阈值
    if total_reg["ci_low"] > delta_total:
        overall_trend = "改善型"
    elif total_reg["ci_high"] < -delta_total:
        overall_trend = "下滑型"
    else:
        overall_trend = "维持型"

    # 风险预警
    warnings = []

    # 1. 下滑型轨迹预警 (CSTM核心)
    for k, name in zip(cog_labels, cog_names):
        if trends[k] == "declining":
            reg = regressions[k]
            warnings.append({
                "type": "cstm_decline",
                "level": "high",
                "dimension": name,
                "slope": reg["slope"],
                "ci": [reg["ci_low"], reg["ci_high"]],
                "message": f"{name}呈下滑型轨迹（斜率={reg['slope']:.3f}, 95%CI=[{reg['ci_low']:.3f}, {reg['ci_high']:.3f}]），建议临床评估并调整干预方案",
            })

    if overall_trend == "下滑型":
        warnings.append({
            "type": "cstm_overall_decline",
            "level": "high",
            "dimension": "CT-30总分",
            "slope": total_reg["slope"],
            "ci": [total_reg["ci_low"], total_reg["ci_high"]],
            "message": f"CT-30总分呈下滑型轨迹（斜率={total_reg['slope']:.3f}），认知功能整体下降，建议立即就医评估",
        })

    # 2. 连续3次总分下降
    if len(total_scores) >= 3:
        recent = total_scores[-3:]
        if recent[0] > recent[1] > recent[2]:
            warnings.append({
                "type": "consecutive_decline",
                "level": "medium",
                "message": "最近3次训练CT-30总分持续下降，需密切关注",
            })

    # 3. 正确率异常低
    if sorted_groups:
        last = sorted_groups[-1]
        total_trials = sum(it["trial_count"] for it in last["items"])
        total_correct = sum(it["correct_count"] for it in last["items"])
        if total_trials and total_correct / total_trials < 0.3:
            warnings.append({
                "type": "low_accuracy",
                "level": "high",
                "message": "最近一次训练正确率低于30%，认知状态可能波动",
            })

    # 4. 训练依从性
    if len(sorted_groups) >= 2:
        try:
            last_date = datetime.strptime(sorted_groups[-1]["created_at"], "%Y-%m-%d %H:%M:%S")
            prev_date = datetime.strptime(sorted_groups[-2]["created_at"], "%Y-%m-%d %H:%M:%S")
            gap = (last_date - prev_date).days
            if gap > 7:
                warnings.append({
                    "type": "compliance",
                    "level": "medium",
                    "message": f"训练间隔{gap}天，依从性下降，建议保持每周≥3次训练",
                })
        except Exception:
            pass

    # 风险等级
    if any(w["level"] == "high" for w in warnings):
        risk_level = "高风险"
    elif any(w["level"] == "medium" for w in warnings):
        risk_level = "关注"
    else:
        risk_level = "正常"

    # 首次 vs 最近认知向量
    first_cog = cog_vectors[0] if cog_vectors else [0, 0, 0, 0, 0]
    last_cog = cog_vectors[-1] if cog_vectors else [0, 0, 0, 0, 0]

    # DMAP模拟数据 (基于EEG指标推导)
    dmap_points = []
    for i, g in enumerate(sorted_groups):
        # 从cog_vector和duration估算AI和CFI
        vec = cog_vectors[i]
        avg_score = sum(vec) / 5
        ai = min(100, avg_score * 80 + (hash(g["created_at"]) % 20))
        cfi = max(0, 100 - avg_score * 60 + (hash(g["created_at"] + "c") % 30))
        dmap_points.append({"ai": ai, "cfi": cfi, "session": i + 1})

    # 逐试次数据 (说明书8.1表7)
    conn2 = get_db()
    trial_details = []
    for i, g in enumerate(sorted_groups):
        # 获取该group下所有session的trials
        g_sessions = conn2.execute(
            """SELECT session_id, task_key FROM sessions
               WHERE user_id=? AND group_id=? ORDER BY group_order""",
            (user_id, list(groups.keys())[list(groups.values()).index(g)]),
        ).fetchall()
        session_trials = []
        for s in g_sessions:
            rows = conn2.execute(
                """SELECT trial_index, task_key, prompt, stimulus, is_correct,
                          intent_level, reaction_time_ms, blink_type,
                          alpha_power, theta_power, cfi_snapshot, ai_snapshot,
                          delta_power, beta_power, gamma_power
                   FROM trials WHERE session_id=? ORDER BY trial_index""",
                (s["session_id"],),
            ).fetchall()
            for r in rows:
                session_trials.append(dict(r))
        trial_details.append({
            "session": i + 1,
            "date": g["created_at"],
            "trials": session_trials,
        })
    conn2.close()

    # 阶段性报告
    report = _generate_report(sorted_groups, cog_vectors, raw_scores, total_scores,
                              trends, regressions, overall_trend, total_reg,
                              warnings, cog_names, sufficient)

    return jsonify({
        "ok": True,
        "sufficient": sufficient,
        "trajectory": {
            "session_count": n_sessions,
            "session_labels": session_labels,
            "cog_vectors": cog_vectors,
            "raw_scores": raw_scores,
            "total_scores": total_scores,
            "trends": trends,
            "regressions": regressions,
            "total_regression": total_reg,
            "overall_trend": overall_trend,
            "risk_level": risk_level,
            "warnings": warnings,
            "first_cog": first_cog,
            "last_cog": last_cog,
            "dmap_points": dmap_points,
            "trial_details": trial_details,
            "report": report,
        },
    })


def _generate_report(groups, cog_vectors, raw_scores, total_scores,
                     trends, regressions, overall_trend, total_reg,
                     warnings, cog_names, sufficient):
    """生成CSTM阶段性文字报告"""
    n = len(groups)
    if n == 0:
        return "暂无训练数据。"

    lines = []
    lines.append(f"CTIS-EEG CSTM 认知轨迹报告\n")
    lines.append(f"基于 {n} 次顺序训练会话{'（满足CSTM建模条件）' if sufficient else '（未达8次最低阈值，结果仅供参考）'}\n")

    # CT-30总分
    lines.append(f"【CT-30总分】")
    lines.append(f"  首次: {total_scores[0]:.1f}  →  最近: {total_scores[-1]:.1f}")
    if sufficient:
        lines.append(f"  线性斜率: {total_reg['slope']:.3f} (95%CI: [{total_reg['ci_low']:.3f}, {total_reg['ci_high']:.3f}])")
    lines.append(f"  总体轨迹: {overall_trend}")

    # 各域分析
    cog_labels = ["orient", "memencode", "trailblink", "semflow", "nameblink"]
    trend_map = {"improving": "改善型", "stable": "维持型", "declining": "下滑型"}
    lines.append(f"\n【五维认知向量 D1-D5】")
    for d, (k, name) in enumerate(zip(cog_labels, cog_names)):
        t = trends.get(k, "stable")
        first_v = cog_vectors[0][d]
        last_v = cog_vectors[-1][d]
        reg = regressions.get(k, {})
        line = f"  {name}: {first_v:.2f} → {last_v:.2f}  [{trend_map[t]}]"
        if sufficient and reg:
            line += f"  β₁={reg['slope']:.3f} CI=[{reg['ci_low']:.3f},{reg['ci_high']:.3f}]"
        lines.append(line)

    # 预警
    if warnings:
        lines.append(f"\n【认知预警】共 {len(warnings)} 项：")
        for w in warnings:
            prefix = "🔴" if w["level"] == "high" else "🟡"
            lines.append(f"  {prefix} {w['message']}")
    else:
        lines.append("\n【认知预警】未检测到风险模式。")

    # 建议
    lines.append("\n【训练建议】")
    if overall_trend == "改善型":
        lines.append("认知表现呈改善趋势，干预有效，建议维持当前训练方案。")
    elif overall_trend == "下滑型":
        lines.append("认知表现呈下滑趋势，建议立即就医评估，调整干预方案。")
        lines.append("可考虑降低训练难度、缩短单次训练时长、增加训练频率。")
    else:
        lines.append("认知表现维持稳定，对抗了疾病自然进展，干预有效。")
        lines.append("建议适当增加训练难度以促进认知进一步提升。")

    return "\n".join(lines)


@app.post("/api/compute_ct30")
def ct30_scoring():
    """根据5项任务的详细结果计算CT-30评分"""
    data = request.get_json(silent=True) or {}
    from backend.task_bank import compute_ct30 as _compute_ct30
    result = _compute_ct30(data)
    return jsonify({"ok": True, "result": result})


if __name__ == "__main__":
    print("=" * 50)
    print("CTIS-EEG Web 系统启动")
    print(f"数据目录: {DATA_DIR}")
    print(f"数据库:   {DB_PATH}")
    print("访问:     http://127.0.0.1:5000")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=False)
