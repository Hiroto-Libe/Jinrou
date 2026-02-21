from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.game import Game, GameMember


def _create_room(client: TestClient, name: str = "Lifecycle Room") -> str:
    res = client.post("/api/rooms", json={"name": name})
    assert res.status_code in (200, 201)
    return res.json()["id"]


def _add_member(client: TestClient, room_id: str, display_name: str):
    res = client.post(
        f"/api/rooms/{room_id}/members",
        json={"display_name": display_name},
    )
    assert res.status_code in (200, 201)
    return res.json()


def _create_game(client: TestClient, room_id: str) -> str:
    res = client.post("/api/games", json={"room_id": room_id})
    assert res.status_code == 200
    return res.json()["id"]


def _seed_members_with_host(client: TestClient, room_id: str, count: int = 6):
    for i in range(count):
        r = client.post(
            f"/api/rooms/{room_id}/roster",
            json={"display_name": f"P{i+1}"},
        )
        assert r.status_code in (200, 201)
    b = client.post(f"/api/rooms/{room_id}/members/bulk_from_roster")
    assert b.status_code in (200, 201)
    assert len(b.json()) == count


def test_member_edit_is_allowed_after_game_finished(client: TestClient, db: Session):
    room_id = _create_room(client, "Finished Editable")
    _seed_members_with_host(client, room_id, 6)

    game_id = _create_game(client, room_id)
    started = client.post(f"/api/games/{game_id}/start")
    assert started.status_code == 200

    game = db.get(Game, game_id)
    game.status = "FINISHED"
    db.add(game)
    db.commit()

    add_after_finish = client.post(
        f"/api/rooms/{room_id}/members",
        json={"display_name": "LateJoin"},
    )
    assert add_after_finish.status_code in (200, 201)

    members = client.get(f"/api/rooms/{room_id}/members")
    assert members.status_code == 200
    names = {m["display_name"] for m in members.json()}
    assert "LateJoin" in names


def test_member_edit_is_blocked_during_started_game(client: TestClient):
    room_id = _create_room(client, "In Progress Locked")
    _seed_members_with_host(client, room_id, 6)

    game_id = _create_game(client, room_id)
    started = client.post(f"/api/games/{game_id}/start")
    assert started.status_code == 200

    blocked_add = client.post(
        f"/api/rooms/{room_id}/members",
        json={"display_name": "Blocked"},
    )
    assert blocked_add.status_code == 400
    assert "in progress" in blocked_add.json()["detail"]

    member_id = client.get(f"/api/rooms/{room_id}/members").json()[0]["id"]
    blocked_delete = client.delete(f"/api/rooms/{room_id}/members/{member_id}")
    assert blocked_delete.status_code == 400


def test_restart_with_same_members_creates_new_game(client: TestClient, db: Session):
    room_id = _create_room(client, "Restart Flow")
    _seed_members_with_host(client, room_id, 6)

    first_game_id = _create_game(client, room_id)
    first_start = client.post(f"/api/games/{first_game_id}/start")
    assert first_start.status_code == 200

    first_game = db.get(Game, first_game_id)
    first_game.status = "FINISHED"
    db.add(first_game)
    db.commit()

    second_game_id = _create_game(client, room_id)
    assert second_game_id != first_game_id

    second_members = client.get(f"/api/games/{second_game_id}/members")
    assert second_members.status_code == 200
    assert len(second_members.json()) == 6

    room = client.get(f"/api/rooms/{room_id}")
    assert room.status_code == 200
    assert room.json()["current_game_id"] == second_game_id


def test_restart_after_win_result_can_start_next_game(client: TestClient, db: Session):
    """
    勝敗確定後（WOLF_WIN / VILLAGE_WIN）に同じRoomで次ゲームを作成し、
    Startできることを確認する。
    """
    room_id = _create_room(client, "Restart After Win")
    _seed_members_with_host(client, room_id, 6)

    first_game_id = _create_game(client, room_id)
    first_start = client.post(f"/api/games/{first_game_id}/start")
    assert first_start.status_code == 200

    first_game = db.get(Game, first_game_id)
    first_game.status = "WOLF_WIN"
    db.add(first_game)
    db.commit()

    second_game_id = _create_game(client, room_id)
    assert second_game_id != first_game_id

    second_start = client.post(f"/api/games/{second_game_id}/start")
    assert second_start.status_code == 200
    started_body = second_start.json()
    assert started_body["id"] == second_game_id
    assert started_body["status"] == "DAY_DISCUSSION"
    assert started_body["started"] is True

    room_after = client.get(f"/api/rooms/{room_id}")
    assert room_after.status_code == 200
    assert room_after.json()["current_game_id"] == second_game_id


def test_second_game_uses_new_member_ids_and_tally_counts_all_votes(client: TestClient, db: Session):
    """
    1ゲーム終了後に2ゲーム目を開始したときに:
    - GameMember.id が1ゲーム目と混ざらない
    - 2ゲーム目の6人投票がすべて集計される
    を確認する。
    """
    room_id = _create_room(client, "Second Game Integrity")
    _seed_members_with_host(client, room_id, 6)

    first_game_id = _create_game(client, room_id)
    assert client.post(f"/api/games/{first_game_id}/start").status_code == 200
    first_members_res = client.get(f"/api/games/{first_game_id}/members")
    assert first_members_res.status_code == 200
    first_members = first_members_res.json()
    first_member_ids = {m["id"] for m in first_members}
    assert len(first_member_ids) == 6

    first_game = db.get(Game, first_game_id)
    first_game.status = "WOLF_WIN"
    db.add(first_game)
    db.commit()

    second_game_id = _create_game(client, room_id)
    start2 = client.post(f"/api/games/{second_game_id}/start")
    assert start2.status_code == 200

    second_members_res = client.get(f"/api/games/{second_game_id}/members")
    assert second_members_res.status_code == 200
    second_members = second_members_res.json()
    second_member_ids = {m["id"] for m in second_members}
    assert len(second_member_ids) == 6
    assert first_member_ids.isdisjoint(second_member_ids)

    # 旧ゲームの member_id で投票しようとしても受理されないこと
    old_voter_id = next(iter(first_member_ids))
    valid_target_id = second_members[0]["id"]
    old_vote = client.post(
        f"/api/games/{second_game_id}/day_vote",
        json={"voter_member_id": old_voter_id, "target_member_id": valid_target_id},
    )
    assert old_vote.status_code == 404

    # 2ゲーム目の全員が投票し、票が6票すべて集計されること
    second_game = db.get(Game, second_game_id)
    second_game.status = "DAY_DISCUSSION"
    second_game.curr_day = second_game.curr_day or 1
    db.add(second_game)
    db.commit()

    villages = [m for m in second_members if m.get("role_type") != "WEREWOLF"]
    assert len(villages) >= 2
    primary_target_id = villages[0]["id"]
    alt_target_id = villages[1]["id"]

    for voter in second_members:
        target_id = primary_target_id if voter["id"] != primary_target_id else alt_target_id
        res_vote = client.post(
            f"/api/games/{second_game_id}/day_vote",
            json={"voter_member_id": voter["id"], "target_member_id": target_id},
        )
        assert res_vote.status_code == 200

    status_res = client.get(f"/api/games/{second_game_id}/day_vote_status")
    assert status_res.status_code == 200
    vote_status = status_res.json()
    assert vote_status["alive_total"] == 6
    assert vote_status["voted_count"] == 6
    assert vote_status["all_done"] is True

    tally_res = client.get(f"/api/games/{second_game_id}/day_tally?day_no=1")
    assert tally_res.status_code == 200
    tally = tally_res.json()
    total_votes = sum(int(item["vote_count"]) for item in tally["items"])
    assert total_votes == 6


def test_delete_room_removes_games_and_game_members(client: TestClient, db: Session):
    room_id = _create_room(client, "Delete Cascade")
    _seed_members_with_host(client, room_id, 6)

    game_id = _create_game(client, room_id)
    assert client.post(f"/api/games/{game_id}/start").status_code == 200

    gm_count_before = (
        db.query(GameMember).filter(GameMember.game_id == game_id).count()
    )
    assert gm_count_before == 6

    delete_res = client.delete(f"/api/rooms/{room_id}")
    assert delete_res.status_code == 204

    room_get = client.get(f"/api/rooms/{room_id}")
    assert room_get.status_code == 404

    game_get = client.get(f"/api/games/{game_id}")
    assert game_get.status_code == 404

    gm_count_after = (
        db.query(GameMember).filter(GameMember.game_id == game_id).count()
    )
    assert gm_count_after == 0
