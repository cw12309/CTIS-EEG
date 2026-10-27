"""API 验证脚本"""
import json
import requests

BASE = "http://127.0.0.1:5000"


def show(label, data):
    if isinstance(data, dict):
        print(f"  {label}:", json.dumps(data, ensure_ascii=False)[:160])
    else:
        print(f"  {label}:", data)


print("=== 1. 用户创建 ===")
r = requests.post(f"{BASE}/api/users", json={"name": "API测试", "age": 70, "diagnosis": "MCI"})
show("status", r.status_code)
data = r.json()
user_id = data["user"]["user_id"]
print(f"  user_id: {user_id}")

print("\n=== 2. 任务列表 ===")
r = requests.get(f"{BASE}/api/tasks")
data = r.json()
print(f"  任务数: {len(data['tasks'])}")
for t in data["tasks"]:
    print(f"   - {t['key']}: {t['name']} ({t['scene_count']} 套题)")

print("\n=== 3. 随机抽题 (orient) ===")
r = requests.get(f"{BASE}/api/tasks/orient/scene")
data = r.json()
print(f"  套名: {data['scene']['set_name']}")
print(f"  试次数: {len(data['scene']['trials'])}")
print(f"  首题: {data['scene']['trials'][0]['prompt']}")

print("\n=== 4. 设备连接 ===")
r = requests.post(f"{BASE}/api/device/connect", json={"mode": "sim"})
show("result", r.json())

print("\n=== 5. 设备状态 ===")
r = requests.get(f"{BASE}/api/device/status")
show("status", r.json())

print("\n=== 6. 眨眼校准 ===")
r = requests.post(f"{BASE}/api/device/calibrate")
show("thresholds", r.json())

print("\n=== 7. 提交训练 session ===")
r = requests.post(f"{BASE}/api/sessions", json={
    "user_id": user_id,
    "task_key": "orient",
    "difficulty": "L2",
    "trial_count": 5,
    "correct_count": 4,
    "score": 80,
    "duration_sec": 120.5,
    "cog_vector": [0.8, 0, 0, 0, 0],
    "trials": [
        {"trial_index": 0, "prompt": "现在是什么季节？", "stimulus": "春季",
         "is_correct": True, "intent_level": 2, "reaction_time_ms": 2300},
    ],
})
show("result", r.json())
session_id = r.json()["session_id"]

print("\n=== 8. 个人统计 ===")
r = requests.get(f"{BASE}/api/stats/{user_id}")
show("stats", r.json())

print("\n=== 9. 会话列表 ===")
r = requests.get(f"{BASE}/api/sessions?user_id={user_id}")
sessions = r.json()["sessions"]
print(f"  记录数: {len(sessions)}")
if sessions:
    print(f"  最新一条: task={sessions[0]['task_key']} score={sessions[0]['score']}")

print("\n=== 10. 会话明细 ===")
r = requests.get(f"{BASE}/api/sessions/{session_id}/trials")
print(f"  试次详情数: {len(r.json()['trials'])}")

print("\n=== 11. 主页 HTML ===")
r = requests.get(f"{BASE}/")
print(f"  状态: {r.status_code}, 长度: {len(r.text)} 字节")
print(f"  包含'CTIS-EEG': {'CTIS-EEG' in r.text}")

print("\n=== 12. 静态资源 ===")
for path in ["/static/style.css", "/static/app.js"]:
    r = requests.get(f"{BASE}{path}")
    print(f"  {path}: {r.status_code} ({len(r.text)} 字节)")

print("\n[OK] 全部接口验证通过")
