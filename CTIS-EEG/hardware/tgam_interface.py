import struct
import threading
import time
from collections import deque
from enum import Enum
from typing import Callable, Optional

import numpy as np
import serial

from config import SAMPLING_RATE, SERIAL_BAUDRATE, SERIAL_TIMEOUT, DEFAULT_COM_PORT


class PacketType(Enum):
    RAW_VALUE = 0x80
    EEG_POWER = 0x83
    ATTENTION = 0x04
    MEDITATION = 0x05
    BLINK = 0x16
    POOR_SIGNAL = 0x02
    HEART_RATE = 0x03


class TGAMInterface(threading.Thread):
    """
    ThinkGear ASIC Module 接口
    支持两种模式:
      - real:   通过 PySerial 读取蓝牙串口
      - legacy: 兼容旧版固定34字节格式 (如现有 9600绘图.py)
      - sim:    模拟生成带眨眼事件的合成 EEG 信号
    """

    def __init__(
        self,
        mode: str = "sim",          # "real" | "legacy" | "sim"
        port: str = DEFAULT_COM_PORT,
        on_raw_sample: Optional[Callable[[int, float], None]] = None,
        on_esense: Optional[Callable[[dict], None]] = None,
    ):
        super().__init__(daemon=True)
        self.mode = mode
        self.port = port
        self.on_raw_sample = on_raw_sample
        self.on_esense = on_esense
        self.running = False

        # 实时原始数据缓冲区 (供信号处理线程消费)
        self.raw_buffer = deque(maxlen=SAMPLING_RATE * 60)  # 1分钟
        self.ts_buffer = deque(maxlen=SAMPLING_RATE * 60)

        # eSense 数据缓存
        self.esense = {
            "delta": 0, "theta": 0, "low_alpha": 0, "high_alpha": 0,
            "low_beta": 0, "high_beta": 0, "low_gamma": 0, "mid_gamma": 0,
            "attention": 0, "meditation": 0, "blink": 0, "poor_signal": 255,
        }

        self._ser: Optional[serial.Serial] = None
        self._sim_t = 0.0
        self._lock = threading.Lock()

    # -------------------- 公共 API --------------------
    def start_stream(self):
        if self.mode in ("real", "legacy"):
            try:
                self._ser = serial.Serial(
                    self.port, SERIAL_BAUDRATE, timeout=SERIAL_TIMEOUT
                )
                time.sleep(2)
            except serial.SerialException as e:
                print(f"[TGAM] 串口打开失败: {e}，自动切换到模拟模式")
                self.mode = "sim"
        self.running = True
        self.start()
        print(f"[TGAM] 已启动，模式={self.mode}")

    def stop_stream(self):
        self.running = False
        if self._ser and self._ser.is_open:
            self._ser.close()
        self.join(timeout=2)

    def get_latest_esense(self) -> dict:
        with self._lock:
            return self.esense.copy()

    def get_raw_snapshot(self, n_samples: int = 512) -> np.ndarray:
        """获取最近 n_samples 个原始样本"""
        with self._lock:
            arr = np.array(self.raw_buffer, dtype=np.float64)
        if len(arr) >= n_samples:
            return arr[-n_samples:]
        return np.zeros(n_samples, dtype=np.float64)

    # -------------------- 线程主循环 --------------------
    def run(self):
        if self.mode == "sim":
            self._run_sim()
        elif self.mode == "legacy":
            self._run_legacy()
        else:
            self._run_real()

    # ---------- 模式 A: 模拟信号 ----------
    def _run_sim(self):
        """生成合成 EEG + 随机眨眼尖峰"""
        dt = 1.0 / SAMPLING_RATE
        t = 0.0
        blink_state = 0        # 0=无, 1=正在生成眨眼
        blink_timer = 0.0
        blink_amp = 0.0
        sample_idx = 0

        while self.running:
            # 基础噪声 (1-30Hz 合成)
            noise = 5.0 * np.sin(2 * np.pi * 10 * t) \
                  + 3.0 * np.sin(2 * np.pi * 6 * t) \
                  + 2.0 * np.random.randn()
            sample = noise

            # 随机触发眨眼 (平均每 4-6 秒一次)
            if blink_state == 0 and np.random.rand() < 0.0008:
                blink_state = 1
                blink_timer = 0.0
                blink_amp = np.random.uniform(80, 250)  # 微伏

            if blink_state == 1:
                # 眨眼波形: 负向尖峰约 150-300ms
                blink_sig = -blink_amp * np.exp(-((blink_timer - 0.15) ** 2) / 0.002)
                sample += blink_sig
                blink_timer += dt
                if blink_timer > 0.4:
                    blink_state = 0

            self._push_raw(sample_idx, sample)
            sample_idx += 1
            t += dt
            time.sleep(dt * 0.8)   # 略快于实时，防止积压

    # ---------- 模式 B: 标准 ThinkGear 协议 ----------
    def _run_real(self):
        """解析标准 TGAM 变长数据包 (0xAA 0xAA header + TLV payload)"""
        payload = bytearray()
        while self.running and self._ser:
            try:
                b = self._ser.read(1)
                if not b:
                    continue
                if b[0] != 0xAA:
                    continue
                b2 = self._ser.read(1)
                if not b2 or b2[0] != 0xAA:
                    continue
                plen = self._ser.read(1)
                if not plen:
                    continue
                length = plen[0]
                if length > 170:
                    continue
                data = self._ser.read(length)
                if len(data) != length:
                    continue
                chk = self._ser.read(1)
                if not chk:
                    continue
                if (sum(data) & 0xFF) != (~chk[0] & 0xFF):
                    continue
                self._parse_tlv(data)
            except Exception as e:
                print(f"[TGAM] 读串口异常: {e}")
                time.sleep(0.5)

    def _parse_tlv(self, data: bytes):
        """解析 payload 中的 code-length-value 序列"""
        i = 0
        while i < len(data):
            code = data[i]
            if code > 0x7F:
                # 扩展代码 (2字节)
                if i + 2 >= len(data):
                    break
                code = (code << 8) | data[i + 1]
                length = data[i + 2]
                i += 3
            else:
                if i + 1 >= len(data):
                    break
                length = data[i + 1]
                i += 2
            if i + length > len(data):
                break
            value = data[i:i + length]
            i += length
            self._dispatch(code, value)

    def _dispatch(self, code: int, value: bytes):
        if code == PacketType.RAW_VALUE.value and len(value) == 2:
            raw = struct.unpack(">h", value)[0]
            # TGAM raw 为 12bit 有符号，范围约 -2048~2047，对应 ~3mV p-p
            # 简单映射为微伏 (非精确校准，但满足算法相对量级)
            uv = raw * 1.5
            self._push_raw(int(time.time() * 1000), uv)

        elif code == PacketType.EEG_POWER.value and len(value) == 24:
            vals = struct.unpack(">8I", value)
            keys = ["delta", "theta", "low_alpha", "high_alpha",
                    "low_beta", "high_beta", "low_gamma", "mid_gamma"]
            with self._lock:
                for k, v in zip(keys, vals):
                    self.esense[k] = v
            if self.on_esense:
                self.on_esense(self.esense.copy())

        elif code == PacketType.ATTENTION.value and len(value) == 1:
            with self._lock:
                self.esense["attention"] = value[0]

        elif code == PacketType.MEDITATION.value and len(value) == 1:
            with self._lock:
                self.esense["meditation"] = value[0]

        elif code == PacketType.BLINK.value and len(value) == 1:
            with self._lock:
                self.esense["blink"] = value[0]

        elif code == PacketType.POOR_SIGNAL.value and len(value) == 1:
            with self._lock:
                self.esense["poor_signal"] = value[0]

    # ---------- 模式 C: 兼容旧版固定 34 字节 ----------
    def _run_legacy(self):
        """兼容 9600绘图.py 的固定 34 字节格式"""
        while self.running and self._ser:
            try:
                b = self._ser.read(1)
                if not b or b[0] != 0xAA:
                    continue
                b2 = self._ser.read(1)
                if not b2 or b2[0] != 0xAA:
                    continue
                data = self._ser.read(34)
                if len(data) != 34:
                    continue
                # 解析格式 (与 9600绘图.py 一致)
                delta       = data[6]  * 256 + data[7]
                theta       = data[9]  * 256 + data[10]
                low_alpha   = data[12] * 256 + data[13]
                high_alpha  = data[15] * 256 + data[16]
                low_beta    = data[18] * 256 + data[19]
                high_beta   = data[21] * 256 + data[22]
                low_gamma   = data[24] * 256 + data[25]
                mid_gamma   = data[27] * 256 + data[28]
                attention   = data[30]
                meditation  = data[32]
                with self._lock:
                    self.esense.update({
                        "delta": delta, "theta": theta,
                        "low_alpha": low_alpha, "high_alpha": high_alpha,
                        "low_beta": low_beta, "high_beta": high_beta,
                        "low_gamma": low_gamma, "mid_gamma": mid_gamma,
                        "attention": attention, "meditation": meditation,
                    })
                if self.on_esense:
                    self.on_esense(self.esense.copy())
                # legacy 模式无 RAW_VALUE，用 0 填充 raw_buffer 保持接口一致
                self._push_raw(int(time.time() * 1000), 0.0)
            except Exception as e:
                print(f"[TGAM-Legacy] 异常: {e}")
                time.sleep(0.5)

    # -------------------- 内部工具 --------------------
    def _push_raw(self, idx: int, uv: float):
        with self._lock:
            self.raw_buffer.append(uv)
            self.ts_buffer.append(idx)
        if self.on_raw_sample:
            self.on_raw_sample(idx, uv)
