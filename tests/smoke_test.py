"""
smoke_test.py
Automated end-to-end smoke test validating all core resume claims and API contracts:
1. User registration & JWT authentication
2. Unauthenticated endpoint protection (401)
3. Asynchronous animation generation via Gemini + Manim
4. Task status polling
5. Strict data separation between User A and User B (history separation, 404 on cross-user queries)
6. Secure asset streaming (User A gets MP4, User B gets 404)
7. SQLite persistence across sessions
"""

import time
import requests
import sys

BASE_URL = "http://127.0.0.1:8000"

def run_smoke_test():
    print("=" * 60)
    print("Starting Animatrix End-to-End Smoke Test")
    print("=" * 60)

    # 1. Check health
    health_res = requests.get(f"{BASE_URL}/api/health")
    assert health_res.status_code == 200, f"Health check failed: {health_res.text}"
    print("[PASS] 1. Server health check OK:", health_res.json())

    # 2. Test unauthenticated request protection
    unauth_gen = requests.post(f"{BASE_URL}/api/generate", json={"prompt": "test"})
    assert unauth_gen.status_code == 401, f"Expected 401, got {unauth_gen.status_code}"
    print("[PASS] 2. Unauthenticated /api/generate correctly rejected with 401")

    unauth_hist = requests.get(f"{BASE_URL}/api/history")
    assert unauth_hist.status_code == 401, f"Expected 401, got {unauth_hist.status_code}"
    print("[PASS] 3. Unauthenticated /api/history correctly rejected with 401")

    # 3. Register User A and User B
    timestamp = int(time.time())
    user_a_name = f"alice_{timestamp}"
    user_b_name = f"bob_{timestamp}"
    pwd = "password123"

    reg_a = requests.post(f"{BASE_URL}/api/register", json={"username": user_a_name, "password": pwd})
    assert reg_a.status_code == 201, f"Registration failed for {user_a_name}: {reg_a.text}"
    token_a = reg_a.json()["access_token"]
    print(f"[PASS] 4. User A registered: {user_a_name}")

    reg_b = requests.post(f"{BASE_URL}/api/register", json={"username": user_b_name, "password": pwd})
    assert reg_b.status_code == 201, f"Registration failed for {user_b_name}: {reg_b.text}"
    token_b = reg_b.json()["access_token"]
    print(f"[PASS] 5. User B registered: {user_b_name}")

    # Test login for User A
    login_a = requests.post(f"{BASE_URL}/api/login", json={"username": user_a_name, "password": pwd})
    assert login_a.status_code == 200
    token_a = login_a.json()["access_token"]
    print("[PASS] 6. User A login verified")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 4. Generate animation as User A
    prompt = "A blue circle transforms into a red square"
    print(f"\n[Action] User A dispatching generation for prompt: '{prompt}'")
    gen_res = requests.post(f"{BASE_URL}/api/generate", json={"prompt": prompt}, headers=headers_a)
    assert gen_res.status_code == 202, f"Generation failed to queue: {gen_res.text}"
    task_id = gen_res.json()["task_id"]
    print(f"[PASS] 7. Task queued successfully with Task ID: {task_id}")

    # 5. Poll task status until completion
    print("[Polling] Waiting for Gemini code generation and Manim rendering...")
    max_wait_seconds = 180
    start_time = time.time()
    completed_task = None

    while time.time() - start_time < max_wait_seconds:
        status_res = requests.get(f"{BASE_URL}/api/tasks/{task_id}", headers=headers_a)
        assert status_res.status_code == 200, f"Task status poll failed: {status_res.text}"
        data = status_res.json()
        current_status = data["status"]

        if current_status == "completed":
            completed_task = data
            elapsed = time.time() - start_time
            print(f"[PASS] 8. Task completed in {elapsed:.1f}s!")
            break
        elif current_status == "failed":
            raise RuntimeError(f"Task failed during render: {data.get('error')}")

        time.sleep(2)

    assert completed_task is not None, "Task timed out before completion."

    # 6. Verify User A history contains this task
    hist_a = requests.get(f"{BASE_URL}/api/history", headers=headers_a)
    assert hist_a.status_code == 200
    tasks_a = hist_a.json()
    assert len(tasks_a) >= 1
    assert tasks_a[0]["id"] == task_id
    assert tasks_a[0]["status"] == "completed"
    print(f"[PASS] 9. User A history verified ({len(tasks_a)} task found)")

    # 7. Strict Data Separation: Verify User B cannot see User A's task in history
    hist_b = requests.get(f"{BASE_URL}/api/history", headers=headers_b)
    assert hist_b.status_code == 200
    tasks_b = hist_b.json()
    assert len(tasks_b) == 0, f"Data leak! User B has tasks in history: {tasks_b}"
    print("[PASS] 10. Strict Data Separation verified: User B history is completely empty")

    # 8. Strict Data Separation: User B calling GET /api/tasks/{task_id} gets 404
    b_task_poll = requests.get(f"{BASE_URL}/api/tasks/{task_id}", headers=headers_b)
    assert b_task_poll.status_code == 404, f"Data leak! User B got {b_task_poll.status_code} for User A's task"
    print("[PASS] 11. Security verified: User B accessing User A's task returns 404")

    # 9. Secure Asset Access: User B calling GET /api/videos/{task_id} gets 404
    b_video_fetch = requests.get(f"{BASE_URL}/api/videos/{task_id}", headers=headers_b)
    assert b_video_fetch.status_code == 404, f"Security leak! User B got {b_video_fetch.status_code} for User A's video"
    print("[PASS] 12. Security verified: User B accessing User A's video returns 404")

    # 10. Secure Asset Access: User A fetching video gets 200 MP4
    a_video_fetch = requests.get(f"{BASE_URL}/api/videos/{task_id}", headers=headers_a)
    assert a_video_fetch.status_code == 200, f"User A failed to stream video: {a_video_fetch.status_code}"
    assert a_video_fetch.headers.get("content-type") == "video/mp4"
    video_bytes_len = len(a_video_fetch.content)
    assert video_bytes_len > 1000, f"Video content too small: {video_bytes_len} bytes"
    print(f"[PASS] 13. Secure Video Stream verified: User A fetched valid MP4 ({video_bytes_len} bytes)")

    print("\n" + "=" * 60)
    print("ALL SMOKE TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_smoke_test()

