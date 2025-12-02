# tests/test_games.py

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


# --- 共通ヘルパー（rooms / profiles テストと同じノリで） ---

def _create_profile(client: TestClient, display_name: str):
    """
    POST /api/profiles でプロフィールを1件作成
    ※ 実装に合わせて payload のキーを調整してください
    """
    payload = {
        "display_name": display_name,
        # 必要なら avatar_url なども付与
    }
    res = client.post("/api/profiles", json=payload)
    assert res.status_code in (200, 201)
    return res.json()


def _create_room(client: TestClient, name: str):
    """
    POST /api/rooms で部屋を1件作成
    ※ owner_profile_id を必須にしている場合は、適宜指定してください
    """
    payload = {"name": name}
    res = client.post("/api/rooms", json=payload)
    assert res.status_code in (200, 201)
    return res.json()


def _join_room_roster_and_members(client: TestClient, room_id: str, display_name: str):
    """
    1. roster に display_name を追加
    2. bulk_from_roster で members に反映
    """
    # roster 追加
    res = client.post(
        f"/api/rooms/{room_id}/roster",
        json={"display_name": display_name},
    )
    assert res.status_code in (200, 201)

    # bulk_from_roster で members へ
    res = client.post(f"/api/rooms/{room_id}/members/bulk_from_roster")
    assert res.status_code in (200, 201)
    return res.json()  # members のリスト想定


def _create_game_from_room(client: TestClient, room_id: str):
    """
    ゲーム作成 API を叩くヘルパー。
    ※ ★ 実装に合わせてエンドポイント・payload を調整してください
       例1: POST /api/games  {"room_id": "..."}
       例2: POST /api/rooms/{room_id}/games  など
    """
    payload = {"room_id": room_id}
    res = client.post("/api/games", json=payload)  # ★必要に応じてパスを変更
    assert res.status_code in (200, 201)
    return res.json()


# --- テスト本体 ---


def test_create_game_and_get_detail(client: TestClient, db: Session):
    """
    部屋＋メンバーからゲームを作成し、
    GET /api/games/{id} で取得できること
    """

    # プロフィール & ルーム & メンバー準備
    prof = _create_profile(client, "Player1")
    room = _create_room(client, "Game Room 1")
    room_id = room["id"]

    # roster & members に参加
    _join_room_roster_and_members(client, room_id, prof["display_name"])

    # ゲーム作成
    created_game = _create_game_from_room(client, room_id)
    game_id = created_game["id"]

    # ゲーム取得
    res_get = client.get(f"/api/games/{game_id}")
    assert res_get.status_code == 200
    body = res_get.json()

    assert body["id"] == game_id
    assert body["room_id"] == room_id
    # status フィールドがあれば確認（実装に合わせてコメント解除）
    # assert body["status"] == "waiting"


def test_get_nonexistent_game_returns_404(client: TestClient, db: Session):
    """
    存在しない game_id で GET すると 404 になること
    """
    res = client.get("/api/games/nonexistent-id-123")
    assert res.status_code == 404


def test_game_members_created_from_room_members(client: TestClient, db: Session):
    """
    部屋メンバーからゲーム参加メンバーが正しく作成されること
    (GET /api/games/{id}/members のようなエンドポイントがある前提)
    """

    # 2人分プロフィール作成
    p1 = _create_profile(client, "Alice")
    p2 = _create_profile(client, "Bob")

    # 部屋作成
    room = _create_room(client, "Game Room 2")
    room_id = room["id"]

    # roster & members に2人参加
    _join_room_roster_and_members(client, room_id, p1["display_name"])
    _join_room_roster_and_members(client, room_id, p2["display_name"])

    # ゲーム作成
    created_game = _create_game_from_room(client, room_id)
    game_id = created_game["id"]

    # ゲーム参加メンバー一覧取得
    # ★ 実装に合わせてパスを調整してください
    res_members = client.get(f"/api/games/{game_id}/members")
    assert res_members.status_code == 200
    members = res_members.json()

    # 少なくとも2名分いることを確認
    assert len(members) >= 2
    names = {m["display_name"] for m in members}
    assert "Alice" in names
    assert "Bob" in names


def test_start_game_changes_status(client: TestClient, db: Session):
    """
    ゲーム開始 API がある場合のステータス遷移テスト。
    実装仕様に合わせて「6人以上で start 成功」とする。
    """

    p = _create_profile(client, "Starter")
    room = _create_room(client, "Start Room")
    room_id = room["id"]

    # 6人以上メンバーを入れる
    for i in range(6):
        _join_room_roster_and_members(client, room_id, f"Player{i+1}")

    game = _create_game_from_room(client, room_id)
    game_id = game["id"]

    # 開始前
    res_before = client.get(f"/api/games/{game_id}")
    assert res_before.status_code == 200
    body_before = res_before.json()
    # 必要なら status の初期値も確認
    # assert body_before["status"] == "WAITING"

    # ゲーム開始
    res_start = client.post(f"/api/games/{game_id}/start")
    assert res_start.status_code in (200, 204)

    # 開始後の status を確認
    res_after = client.get(f"/api/games/{game_id}")
    assert res_after.status_code == 200
    body_after = res_after.json()
    assert body_after["status"] == "NIGHT"


def test_start_game_twice_returns_error(client: TestClient, db: Session):
    """
    すでに開始されたゲームをもう一度開始しようとすると
    400 や 409 などのエラーになる仕様。
    実装仕様に合わせて「6人以上で1回目の start は成功」とする。
    """

    p = _create_profile(client, "DoubleStarter")
    room = _create_room(client, "Double Start Room")
    room_id = room["id"]

    # 6人以上メンバーを入れる
    for i in range(6):
        _join_room_roster_and_members(client, room_id, f"Player{i+1}")

    game = _create_game_from_room(client, room_id)
    game_id = game["id"]

    # 1回目の start は成功
    res_start1 = client.post(f"/api/games/{game_id}/start")
    assert res_start1.status_code in (200, 204)

    # 2回目の start はエラー（実装では 400 "Game already started"）
    res_start2 = client.post(f"/api/games/{game_id}/start")
    assert res_start2.status_code in (400, 409)
