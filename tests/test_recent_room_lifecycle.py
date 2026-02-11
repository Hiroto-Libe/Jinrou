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
