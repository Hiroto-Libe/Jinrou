# tests/test_full_game_flow.py

import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.room import Room, RoomMember
from app.models.game import GameMember
from app.api.v1.games import decide_roles


def _create_room_with_members(db: Session, member_count: int = 8) -> Room:
    """DB に部屋と部屋メンバーをまとめて作るヘルパー"""
    room = Room(
        id=str(uuid.uuid4()),
        name="test room",
        # 必須カラムが他にもあればここで追加
    )
    db.add(room)
    db.flush()  # room.id を使いたいので flush

    for i in range(1, member_count + 1):
        rm = RoomMember(
            id=str(uuid.uuid4()),
            room_id=room.id,
            display_name=f"Player{i}",
            avatar_url=None,
            is_host=(i == 1),
            # order_no が NOT NULL ならここで設定
            # order_no=i,
        )
        db.add(rm)

    db.commit()
    db.refresh(room)
    return room


def test_full_game_flow_with_role_assignment(db: Session, client: TestClient):
    """
    部屋 → メンバー → ゲーム作成 → /start で役職配布までを
    一気に確認する統合テスト。
    """
    member_count = 8
    room = _create_room_with_members(db, member_count)

    # ゲーム作成
    res_create = client.post("/api/games", json={"room_id": room.id})
    assert res_create.status_code == 200
    game = res_create.json()
    game_id = game["id"]

    # ゲーム開始（役職配布も含む）
    res_start = client.post(f"/api/games/{game_id}/start")
    assert res_start.status_code == 200

    # DB から game_members を取得して確認
    members = (
        db.query(GameMember)
        .filter(GameMember.game_id == game_id)
        .order_by(GameMember.order_no.asc())
        .all()
    )

    assert len(members) == member_count

    # 全員に role_type / team が入っている
    assert all(m.role_type is not None for m in members)
    assert all(m.team is not None for m in members)

    # decide_roles の構成と一致していること
    expected_roles = sorted(role for role, _team in decide_roles(member_count))
    actual_roles = sorted(m.role_type for m in members)
    assert actual_roles == expected_roles

    wolf_team_count = sum(1 for m in members if m.team == "WOLF")
    village_team_count = sum(1 for m in members if m.team == "VILLAGE")
    assert wolf_team_count >= 1
    assert village_team_count >= 1


def test_start_game_twice_returns_400(db: Session, client: TestClient):
    """同じゲームで /start を2回叩くと 2回目は 400 になることを確認"""
    room = _create_room_with_members(db, member_count=8)

    res_create = client.post("/api/games", json={"room_id": room.id})
    assert res_create.status_code == 200
    game_id = res_create.json()["id"]

    # 1回目は成功
    res1 = client.post(f"/api/games/{game_id}/start")
    assert res1.status_code == 200

    # 2回目は 400
    res2 = client.post(f"/api/games/{game_id}/start")
    assert res2.status_code == 400
    body = res2.json()
    assert body["detail"] == "Game already started"


def test_start_game_too_few_players_returns_400(db: Session, client: TestClient):
    """プレイヤー人数が足りない場合に 400 を返すことを確認"""
    room = _create_room_with_members(db, member_count=5)

    res_create = client.post("/api/games", json={"room_id": room.id})
    assert res_create.status_code == 200
    game_id = res_create.json()["id"]

    res_start = client.post(f"/api/games/{game_id}/start")
    assert res_start.status_code == 400
    body = res_start.json()
    assert "Need at least 6 players" in body["detail"]


def test_start_nonexistent_game_returns_404(client: TestClient):
    """存在しないゲームIDで /start を叩いた場合に 404 になることを確認"""
    fake_game_id = str(uuid.uuid4())

    res = client.post(f"/api/games/{fake_game_id}/start")
    assert res.status_code == 404
    body = res.json()
    assert body["detail"] == "Game not found"
