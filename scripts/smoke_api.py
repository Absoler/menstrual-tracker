"""API 冒烟测试：先启动服务，再运行本脚本验证主要接口。

用法：
    .venv/bin/python -m uvicorn app.main:app --port 8000
    .venv/bin/python scripts/smoke_api.py
"""

import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"


def call(method, path, body=None, token=None):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    payload = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data=payload) as res:
            return res.status, json.loads(res.read())
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read())


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (("  | " + detail) if detail else ""))
    if not ok:
        sys.exit(1)


def main():
    suffix = str(int(time.time()))
    alice = {"username": "alice_" + suffix, "password": "secret123"}
    bob = {"username": "bob_" + suffix, "password": "secret123"}

    status, data = call("POST", "/api/auth/register", alice)
    check("注册", status == 200 and "token" in data)
    alice_token = data["token"]

    status, data = call("POST", "/api/auth/login", alice)
    check("登录", status == 200 and data["username"] == alice["username"])

    status, data = call("GET", "/api/auth/me", token=alice_token)
    check("当前用户", status == 200 and data["username"] == alice["username"])

    for date, flow in [
        ("2026-07-07", "light"),
        ("2026-07-08", "medium"),
        ("2026-08-04", "light"),
        ("2026-08-05", "spotting"),
    ]:
        status, _ = call("PUT", "/api/records/" + date, {"flow": flow}, alice_token)
        check("写入记录 " + date, status == 200)

    status, data = call("GET", "/api/records?month=2026-08", token=alice_token)
    check("按月取记录", status == 200 and len(data["records"]) == 2)

    status, pred = call("GET", "/api/predictions", token=alice_token)
    check("预测状态", status == 200 and pred["status"] == "ok")
    check("下次月经 2026-09-01", pred["next_period"] == "2026-09-01", pred["next_period"])
    check("排卵日 2026-08-18", pred["ovulation"] == "2026-08-18", pred["ovulation"])

    status, data = call("GET", "/api/notifications", token=alice_token)
    check("通知接口", status == 200 and isinstance(data["notifications"], list))

    status, _ = call("POST", "/api/auth/register", bob)
    check("注册第二用户", status == 200)
    _, bob_login = call("POST", "/api/auth/login", bob)
    status, data = call("GET", "/api/records?month=2026-08", token=bob_login["token"])
    check("用户数据隔离", status == 200 and data["records"] == [])

    status, _ = call("POST", "/api/auth/login",
                     {"username": alice["username"], "password": "wrong"})
    check("错误密码被拒", status == 401)

    with urllib.request.urlopen(BASE + "/") as res:
        html = res.read().decode()
    check("静态首页", res.status == 200 and "月经记录助手" in html)

    print("\n全部通过 ✓")


if __name__ == "__main__":
    main()
