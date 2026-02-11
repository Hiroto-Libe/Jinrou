# tests/test_rooms.py
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app


def test_create_room_and_join_and_list_members(client: TestClient, db: Session):
    # 1. 部屋作成
    res = client.post("/api/rooms", json={"name": "Test Room"})
    assert res.status_code in (200, 201)
    room = res.json()
    room_id = room["id"]

    # 2. roster にプレイヤー1人追加
    roster_payload = {"display_name": "Player1"}
    res = client.post(f"/api/rooms/{room_id}/roster", json=roster_payload)
    assert res.status_code in (200, 201)

    # 3. bulk_from_roster で members へ反映
    res = client.post(f"/api/rooms/{room_id}/members/bulk_from_roster")
    assert res.status_code in (200, 201)

    # 4. members を取得して1人いることを確認
    res = client.get(f"/api/rooms/{room_id}/members")
    assert res.status_code == 200
    members = res.json()
    assert len(members) == 1
    assert members[0]["display_name"] == "Player1"



def test_join_same_display_name_twice(client: TestClient, db: Session):
    """
    挙動確認（異常系・仕様確認用）:
    - 同じ display_name を 2回 roster に追加したときの挙動をテスト
    - 実装に合わせて以下のどちらかに寄せてください
      - (A) 2回目は 400 / 409 などのエラー
      - (B) 2回とも成功し、members に 2名登録される
    """

    # --- 1. 部屋を作成 ---
    res = client.post("/api/rooms", json={"name": "Duplicate Join Test"})
    assert res.status_code in (200, 201)
    room_id = res.json()["id"]

    # --- 2. 同じ display_name で2回 roster に追加 ---
    payload = {"display_name": "Bob"}

    res1 = client.post(f"/api/rooms/{room_id}/roster", json=payload)
    assert res1.status_code in (200, 201)

    res2 = client.post(f"/api/rooms/{room_id}/roster", json=payload)

    # ↓ここは実装に合わせて分岐
    # 例(A): 2回目はエラーにしたい場合
    # assert res2.status_code == 400

    # 例(B): 2回とも OK にして members に2名並ぶ仕様にしたい場合
    assert res2.status_code in (200, 201)

    # roster から members へ登録
    res = client.post(f"/api/rooms/{room_id}/members/bulk_from_roster")
    assert res.status_code in (200, 201)

    res = client.get(f"/api/rooms/{room_id}/members")
    assert res.status_code == 200
    members = res.json()

    # ここも仕様に合わせて選んでください
    # 例(B) の場合:
    assert len(members) == 2
    assert all(m["display_name"] == "Bob" for m in members)


def test_get_members_of_nonexistent_room_returns_404(client: TestClient):
    """
    存在しない room_id で /members を叩いたとき 404 が返ることの確認
    """
    fake_room_id = "non-existent-room-id"
    res = client.get(f"/api/rooms/{fake_room_id}/members")
    assert res.status_code == 404

# tests/test_rooms.py

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_list_rooms_returns_created_rooms(client: TestClient, db: Session):
    # 部屋を2つ作成
    res1 = client.post("/api/rooms", json={"name": "Room A"})
    res2 = client.post("/api/rooms", json={"name": "Room B"})
    assert res1.status_code in (200, 201)
    assert res2.status_code in (200, 201)

    # 一覧取得
    res = client.get("/api/rooms")
    assert res.status_code == 200

    rooms = res.json()
    # 2つ以上あるはず
    assert len(rooms) >= 2

    names = {r["name"] for r in rooms}
    assert "Room A" in names
    assert "Room B" in names


def test_list_roster_after_join(client: TestClient, db: Session):
    # 部屋作成
    res = client.post("/api/rooms", json={"name": "Roster Test Room"})
    assert res.status_code in (200, 201)
    room_id = res.json()["id"]

    # roster に 2人追加（既存テストと同じ payload 形式）
    payload1 = {"display_name": "Alice"}
    payload2 = {"display_name": "Bob"}

    res1 = client.post(f"/api/rooms/{room_id}/roster", json=payload1)
    res2 = client.post(f"/api/rooms/{room_id}/roster", json=payload2)
    assert res1.status_code in (200, 201)
    assert res2.status_code in (200, 201)

    # roster 一覧取得
    res_list = client.get(f"/api/rooms/{room_id}/roster")
    assert res_list.status_code == 200

    roster = res_list.json()
    assert len(roster) == 2

    display_names = {item["display_name"] for item in roster}
    assert "Alice" in display_names
    assert "Bob" in display_names


def test_get_roster_of_nonexistent_room_returns_404(client: TestClient, db: Session):
    fake_room_id = "non-existent-room-id"
    res = client.get(f"/api/rooms/{fake_room_id}/roster")
    assert res.status_code == 404


def test_bulk_from_roster_on_empty_roster_returns_empty_list(client: TestClient, db: Session):
    # 部屋作成
    res = client.post("/api/rooms", json={"name": "Empty Roster Room"})
    assert res.status_code in (200, 201)
    room_id = res.json()["id"]

    # roster は誰もいない状態で bulk_from_roster
    res = client.post(f"/api/rooms/{room_id}/members/bulk_from_roster")
    assert res.status_code == 200

    members = res.json()
    assert members == []  # 空リストを期待


def test_bulk_from_roster_of_nonexistent_room_returns_404(client: TestClient, db: Session):
    fake_room_id = "non-existent-room-id"
    res = client.post(f"/api/rooms/{fake_room_id}/members/bulk_from_roster")
    assert res.status_code == 404


def test_members_display_names_created_from_roster(client: TestClient, db: Session):
    # 部屋作成
    res = client.post("/api/rooms", json={"name": "Members From Roster Room"})
    assert res.status_code in (200, 201)
    room_id = res.json()["id"]

    # roster に2人追加
    client.post(f"/api/rooms/{room_id}/roster", json={"display_name": "Alice"})
    client.post(f"/api/rooms/{room_id}/roster", json={"display_name": "Bob"})

    # members を作成
    res = client.post(f"/api/rooms/{room_id}/members/bulk_from_roster")
    assert res.status_code in (200, 201)

    # members 一覧を取得して中身確認
    res = client.get(f"/api/rooms/{room_id}/members")
    assert res.status_code == 200
    members = res.json()

    assert len(members) == 2
    names = {m["display_name"] for m in members}
    assert names == {"Alice", "Bob"}


def test_add_and_remove_room_member(client: TestClient, db: Session):
    res = client.post("/api/rooms", json={"name": "Edit Members Room"})
    assert res.status_code in (200, 201)
    room_id = res.json()["id"]

    add1 = client.post(f"/api/rooms/{room_id}/members", json={"display_name": "M1"})
    add2 = client.post(f"/api/rooms/{room_id}/members", json={"display_name": "M2"})
    assert add1.status_code in (200, 201)
    assert add2.status_code in (200, 201)

    members = client.get(f"/api/rooms/{room_id}/members").json()
    assert len(members) == 2

    member_id = members[0]["id"]
    rm = client.delete(f"/api/rooms/{room_id}/members/{member_id}")
    assert rm.status_code == 204

    members_after = client.get(f"/api/rooms/{room_id}/members").json()
    assert len(members_after) == 1


def test_cannot_edit_members_while_game_in_progress(client: TestClient, db: Session):
    res = client.post("/api/rooms", json={"name": "Locked Members Room"})
    assert res.status_code in (200, 201)
    room_id = res.json()["id"]

    add = client.post(f"/api/rooms/{room_id}/members", json={"display_name": "P1"})
    assert add.status_code in (200, 201)
    member_id = add.json()["id"]

    # current_game_id が設定される（WAITING）
    game = client.post("/api/games", json={"room_id": room_id})
    assert game.status_code == 200

    add_blocked = client.post(f"/api/rooms/{room_id}/members", json={"display_name": "P2"})
    assert add_blocked.status_code == 400

    del_blocked = client.delete(f"/api/rooms/{room_id}/members/{member_id}")
    assert del_blocked.status_code == 400


def test_delete_room_removes_related_game_data(client: TestClient, db: Session):
    res = client.post("/api/rooms", json={"name": "Delete Room"})
    assert res.status_code in (200, 201)
    room_id = res.json()["id"]

    # ゲーム作成に必要なメンバを追加
    for i in range(6):
        add = client.post(f"/api/rooms/{room_id}/members", json={"display_name": f"P{i+1}"})
        assert add.status_code in (200, 201)

    g = client.post("/api/games", json={"room_id": room_id})
    assert g.status_code == 200
    game_id = g.json()["id"]

    d = client.delete(f"/api/rooms/{room_id}")
    assert d.status_code == 204

    room_get = client.get(f"/api/rooms/{room_id}")
    assert room_get.status_code == 404

    game_get = client.get(f"/api/games/{game_id}")
    assert game_get.status_code == 404
