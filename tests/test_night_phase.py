# tests/test_night_phase.py

import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.room import Room, RoomMember
from app.models.game import Game, GameMember


def _create_room_with_members(db: Session, member_count: int = 8) -> Room:
    """DB に部屋と部屋メンバーをまとめて作るヘルパー"""
    room = Room(
        id=str(uuid.uuid4()),
        name="night test room",
    )
    db.add(room)
    db.flush()

    for i in range(1, member_count + 1):
        rm = RoomMember(
            id=str(uuid.uuid4()),
            room_id=room.id,
            display_name=f"Player{i}",
            avatar_url=None,
        )
        db.add(rm)

    db.commit()
    db.refresh(room)
    return room


def _setup_started_game(db: Session, client: TestClient, member_count: int = 8):
    """
    部屋→メンバー→ゲーム作成→/start までをまとめて実行し、
    (game_id, members) を返すヘルパー。
    """
    room = _create_room_with_members(db, member_count)

    # ゲーム作成
    res_create = client.post("/api/games", json={"room_id": room.id})
    assert res_create.status_code == 200
    game_id = res_create.json()["id"]

    # ゲーム開始（ここで役職配布 & status=NIGHT）
    res_start = client.post(f"/api/games/{game_id}/start")
    assert res_start.status_code == 200

    # DB からメンバー取得
    members = (
        db.query(GameMember)
        .filter(GameMember.game_id == game_id)
        .order_by(GameMember.order_no.asc())
        .all()
    )
    assert len(members) == member_count

    return game_id, members


def test_wolf_vote_requires_night_phase(db: Session, client: TestClient):
    """
    ゲームが NIGHT フェーズでない状態で /wolves/vote を叩くと
    400 'Game is not in NIGHT phase' になることを確認する。
    """
    game_id, members = _setup_started_game(db, client, member_count=8)

    # いったんゲームを DAY 側に書き換えて、前提違反パターンを作る
    game = db.get(Game, game_id)
    game.status = "DAY_DISCUSSION"
    db.add(game)
    db.commit()

    wolves = [m for m in members if m.team == "WOLF"]
    villages = [m for m in members if m.team == "VILLAGE"]

    assert len(wolves) >= 1
    assert len(villages) >= 1

    wolf = wolves[0]
    target = villages[0]

    res_vote = client.post(
        f"/api/games/{game_id}/wolves/vote",
        json={
            "wolf_member_id": wolf.id,
            "target_member_id": target.id,
            "priority_level": 1,
        },
    )

    assert res_vote.status_code == 400
    body = res_vote.json()
    assert body["detail"] == "Game is not in NIGHT phase"


def test_wolf_vote_and_resolve_night_kills_target(db: Session, client: TestClient):
    """
    NIGHT フェーズで:
      - 人狼が村人を1人指定して投票
      - resolve_night_simple でその村人が死亡扱いになる
    という一連の流れを検証する。
    """
    game_id, members = _setup_started_game(db, client, member_count=8)

    # この時点では start_game により status="NIGHT" のはず
    game = db.get(Game, game_id)
    assert game.status == "NIGHT"

    wolves = [m for m in members if m.team == "WOLF"]
    villages = [m for m in members if m.team == "VILLAGE"]

    assert len(wolves) >= 1
    assert len(villages) >= 1

    wolf = wolves[0]
    target = villages[0]

    # 開始時点では生きているはず
    assert target.alive is True

    # --- 1. 人狼投票 API を叩く ---
    res_vote = client.post(
        f"/api/games/{game_id}/wolves/vote",
        json={
            "wolf_member_id": wolf.id,
            "target_member_id": target.id,
            "priority_level": 1,
        },
    )
    assert res_vote.status_code == 200
    data = res_vote.json()
    assert data["wolf_member_id"] == wolf.id
    assert data["target_member_id"] == target.id

    # --- 2. 夜解決 API を叩く ---
    res_resolve = client.post(f"/api/games/{game_id}/resolve_night_simple")
    assert res_resolve.status_code == 200

    # --- 3. メンバー一覧 API でターゲットが死亡扱いになっていることを確認 ---
    res_members_after = client.get(f"/api/games/{game_id}/members")
    assert res_members_after.status_code == 200
    members_after = res_members_after.json()

    target_after = next(m for m in members_after if m["id"] == target.id)
    assert target_after["alive"] is False



def test_wolf_vote_by_non_wolf_returns_400(db: Session, client: TestClient):
    """
    NIGHT フェーズで、人狼以外が /wolves/vote を叩いた場合に
    400 'Member is not a werewolf' になることを確認する。
    """
    game_id, members = _setup_started_game(db, client, member_count=8)

    game = db.get(Game, game_id)
    assert game.status == "NIGHT"

    wolves = [m for m in members if m.team == "WOLF"]
    villages = [m for m in members if m.team == "VILLAGE"]

    assert len(wolves) >= 1
    assert len(villages) >= 2  # 投票者とターゲット用

    non_wolf_voter = villages[0]
    target = villages[1]

    res_vote = client.post(
        f"/api/games/{game_id}/wolves/vote",
        json={
            "wolf_member_id": non_wolf_voter.id,  # あえて人狼以外を指定
            "target_member_id": target.id,
            "priority_level": 1,
        },
    )

    assert res_vote.status_code == 400
    body = res_vote.json()
    assert body["detail"] == "Member is not a werewolf"
