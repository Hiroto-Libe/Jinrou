# tests/test_day_phase.py

from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.game import Game, GameMember
from app.models.room import RoomMember


def _setup_started_game(db: Session, client: TestClient, member_count: int = 8):
    """
    night_phase のテストでも使っているヘルパーと同じものを
    ここでも import して使うか、必要であれば共通モジュールに切り出す。
    ここでは既に tests/test_night_phase.py にある前提。
    """
    from tests.test_night_phase import _setup_started_game as _orig
    return _orig(db, client, member_count=member_count)


def test_day_vote_requires_day_discussion_phase(db: Session, client: TestClient):
    """
    game.status が DAY_DISCUSSION 以外のときは 400 になること、
    DAY_DISCUSSION にしてやれば 200 になることを確認。
    """
    game_id, members = _setup_started_game(db, client, member_count=8)

    game = db.get(Game, game_id)
    # start_game 直後は DAY_DISCUSSION のはず
    assert game.status == "DAY_DISCUSSION"

    voter = members[0]
    target = members[1]

    # --- 1. NIGHT フェーズで叩くと 400 ---
    game.status = "NIGHT"
    db.add(game)
    db.commit()

    res = client.post(
        f"/api/games/{game_id}/day_vote",
        json={
            "voter_member_id": voter.id,
            "target_member_id": target.id,
        },
    )
    assert res.status_code == 400
    body = res.json()
    assert body["detail"] == "Game is not in DAY_DISCUSSION phase"

    # --- 2. ステータスを DAY_DISCUSSION にして再トライ ---
    game.status = "DAY_DISCUSSION"
    game.curr_day = game.curr_day or 1  # 念のため 1 に初期化しておく
    db.add(game)
    db.commit()

    res2 = client.post(
        f"/api/games/{game_id}/day_vote",
        json={
            "voter_member_id": voter.id,
            "target_member_id": target.id,
        },
    )
    assert res2.status_code == 200
    data = res2.json()
    assert data["voter_member_id"] == voter.id
    assert data["target_member_id"] == target.id

def test_day_vote_and_resolve_day_executes_target(db: Session, client: TestClient):
    """
    DAY_DISCUSSION フェーズで:
      - 生存者全員が同じターゲットに投票
      - resolve_day_simple を叩く
      - そのターゲットが alive=False になる
    一連の流れを検証する。
    """
    game_id, members = _setup_started_game(db, client, member_count=8)

    # とりあえず夜はすっ飛ばして、手動で昼の議論フェーズに持っていく
    game = db.get(Game, game_id)
    game.status = "DAY_DISCUSSION"
    game.curr_day = game.curr_day or 1
    db.add(game)
    db.commit()

    # 生存メンバー一覧（開始直後なので全員 True のはず）
    alive_members = [m for m in members if m.alive]
    assert len(alive_members) >= 2

    # 投票ターゲットは先頭、その他全員がその人に投票
    target = alive_members[0]
    voters = alive_members[1:]

    for voter in voters:
        res = client.post(
            f"/api/games/{game_id}/day_vote",
            json={
                "voter_member_id": voter.id,
                "target_member_id": target.id,
            },
        )
        assert res.status_code == 200

    # --- 昼の解決を実行 ---
    host_room_member = (
        db.query(RoomMember)
        .filter(RoomMember.room_id == game.room_id, RoomMember.is_host == True)
        .first()
    )
    assert host_room_member is not None
    host_game_member = next(
        m for m in members if m.room_member_id == host_room_member.id
    )

    res_resolve = client.post(
        f"/api/games/{game_id}/resolve_day_simple",
        json={"requester_member_id": host_game_member.id},
    )
    assert res_resolve.status_code == 200

    # --- API 経由でメンバー情報を取得し、ターゲットが死亡扱いになっていることを確認 ---
    res_members_after = client.get(f"/api/games/{game_id}/members")
    assert res_members_after.status_code == 200
    members_after = res_members_after.json()

    # id でターゲットを特定
    target_after = next(m for m in members_after if m["id"] == target.id)
    assert target_after["alive"] is False

    # ついでに、ゲーム側の last_executed_member_id もターゲットになっていることを確認
    game_after = db.get(Game, game_id)
    db.refresh(game_after)
    assert game_after.last_executed_member_id == target.id

