"""回归：写成功后台账墙不得再把新行藏起来；按编号打开卡片同样不得藏行。"""
import os
import tempfile

_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"

import claimer

claimer._stop.set()  # 测试里不让认领线程碰 sqlite 库

import api

client = api.app.test_client()


def login(username, password):
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return {"Authorization": "Bearer " + res.get_json()["access_token"]}


def submit(headers, chainage, delta_mm):
    res = client.post("/api/logs", json={"chainage": chainage, "delta_mm": delta_mm}, headers=headers)
    assert res.status_code == 201
    return res.get_json()["id"]


def wall_ids(headers):
    res = client.get("/api/logs", headers=headers)
    assert res.status_code == 200
    return {row["id"] for row in res.get_json()}


def test_new_row_visible_on_wall_after_write():
    headers = login("surveyor", "surv123456")
    new_id = submit(headers, "K20+050", 1.1)
    assert new_id > 2  # 非种子行，正是以前会被台账重算藏掉的行
    assert new_id in wall_ids(headers)


def test_inspector_readonly_but_sees_new_row():
    writer = login("surveyor", "surv123456")
    new_id = submit(writer, "K21+500", 4.2)
    reader = login("inspector", "insp123456")
    res = client.post("/api/logs", json={"chainage": "K0+000", "delta_mm": 1.0}, headers=reader)
    assert res.status_code == 403  # 巡检岗只读
    assert new_id in wall_ids(reader)  # 但监理能在台账墙看见刚进库的新行


def test_open_card_by_id_not_hidden():
    headers = login("surveyor", "surv123456")
    new_id = submit(headers, "K22+000", 2.5)
    res = client.get(f"/api/logs/{new_id}", headers=headers)
    assert res.status_code == 200
    assert res.get_json()["id"] == new_id


def test_rapid_fire_writes_all_stay_visible():
    headers = login("surveyor", "surv123456")
    ids = [submit(headers, f"K3{i}+000", 0.5 * i) for i in range(5)]
    visible = wall_ids(headers)
    for new_id in ids:
        assert new_id in visible
