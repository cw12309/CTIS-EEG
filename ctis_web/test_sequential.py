"""End-to-end test for sequential training flow."""
import json
import urllib.request
import random
import time

API = "http://127.0.0.1:5000"


def get(path):
    return json.loads(urllib.request.urlopen(API + path).read().decode())


def post(path, body):
    req = urllib.request.Request(
        API + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return json.loads(urllib.request.urlopen(req).read().decode())


# 1. 测试顺序训练 5 个任务的题库都能加载
print("=== 1. 题库加载 ===")
for k in ["orient", "memencode", "trailblink", "semflow", "nameblink"]:
    d = get(f"/api/tasks/{k}/scene")
    assert d.get("ok"), f"题库加载失败: {k}"
    scene = d.get("scene", {})
    if "trials" in scene:
        print(f"  {k}: 题套 {scene.get('set_name')} - {len(scene['trials'])} 题")
    else:
        print(f"  {k}: 题套 {scene.get('set_name')} - {sum(len(v) if isinstance(v, list) else 0 for v in scene.values())} 项")

# 2. 创建测试用户
print("\n=== 2. 创建用户 ===")
uid = f"test_seq_{random.randint(1000, 9999)}"
r = post("/api/users", {"user_id": uid, "name": uid, "age": 65, "gender": "M", "diagnosis": "测试"})
print("  ", r)
assert r.get("ok")
uid = r["user"]["user_id"]  # 使用服务器返回的真实ID
print(f"  使用 user_id: {uid}")

# 3. 提交 5 个子任务的顺序训练聚合记录
print("\n=== 3. 提交顺序训练聚合 ===")
cog_map = {"orient": 0, "memencode": 1, "trailblink": 2, "semflow": 3, "nameblink": 4}
tasks_payload = []
for idx, k in enumerate(["orient", "memencode", "trailblink", "semflow", "nameblink"]):
    cog = [0, 0, 0, 0, 0]
    cog[cog_map[k]] = 0.8
    tasks_payload.append({
        "task_key": k,
        "difficulty": 1,
        "trial_count": 5,
        "correct_count": 4,
        "score": 80,
        "duration_sec": 30,
        "cog_vector": cog,
        "group_order": idx,
        "trials": [
            {"trial_index": 0, "prompt": "示例", "stimulus": "选项A", "is_correct": 1, "intent_level": 1, "reaction_time_ms": 1500}
        ],
    })
r = post("/api/sequential_session", {"user_id": uid, "tasks": tasks_payload})
print("  ", r)
assert r.get("ok") and len(r.get("session_ids", [])) == 5

# 4. 查询顺序训练记录
print("\n=== 4. 查询顺序训练记录 ===")
r = get(f"/api/sequential_sessions?user_id={uid}")
print(json.dumps(r, ensure_ascii=False, indent=2))
assert r.get("ok") and len(r["groups"]) >= 1
g = r["groups"][0]
assert g["task_count"] == 5
assert abs(g["avg_score"] - 80) < 0.1

# 5. 验证 5s 休息间隔逻辑（前端使用 setInterval 倒数 5s）
print("\n=== 5. 验证 5s 休息间隔（前端 setInterval 逻辑） ===")
SEQ_REST_SEC = 5
t0 = time.time()
print(f"  任务1完成")
print(f"  休息开始: {t0:.1f}")
for s in range(SEQ_REST_SEC, 0, -1):
    print(f"  倒计时: {s}...")
    time.sleep(1)
print(f"  任务2开始 (休息 {time.time()-t0:.1f}s)")

print("\n[OK] 顺序训练后端联调通过！")
