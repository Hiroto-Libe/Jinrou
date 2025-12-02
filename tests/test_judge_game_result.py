# tests/test_judge_game_result.py

import uuid
from sqlalchemy.orm import Session

from app.models.game import GameMember
from app.api.v1.games import _judge_game_result


def _add_member(
    db: Session,
    game_id: str,
    *,
    team: str,
    alive: bool = True,
    order_no: int = 0,
    role_type: str | None = None,
) -> GameMember:
    """
    _judge_game_result は Game テーブルを参照しないので、
    Game 行は作らず GameMember だけを追加するヘルパー。
    """
    if role_type is None:
        role_type = "WEREWOLF" if team == "WOLF" else "VILLAGER"

    m = GameMember(
        id=str(uuid.uuid4()),
        game_id=game_id,
        room_member_id=str(uuid.uuid4()),
        display_name=f"member-{order_no}",
        avatar_url=None,
        role_type=role_type,
        team=team,
        alive=alive,
        order_no=order_no,
    )
    db.add(m)
    return m


def test_judge_game_result_village_win_when_all_wolves_dead(db: Session):
    """
    生きている人狼が 0 人なら VILLAGE_WIN になること。
    """
    game_id = str(uuid.uuid4())

    # 生存村人 3
    _add_member(db, game_id, team="VILLAGE", alive=True, order_no=1)
    _add_member(db, game_id, team="VILLAGE", alive=True, order_no=2)
    _add_member(db, game_id, team="VILLAGE", alive=True, order_no=3)

    # 死亡人狼 2
    _add_member(db, game_id, team="WOLF", alive=False, order_no=4, role_type="WEREWOLF")
    _add_member(db, game_id, team="WOLF", alive=False, order_no=5, role_type="WEREWOLF")

    db.commit()

    result = _judge_game_result(game_id, db)

    assert result["result"] == "VILLAGE_WIN"
    assert result["wolf_alive"] == 0
    assert result["village_alive"] == 3
    assert result["reason"] == "All werewolves are dead."


def test_judge_game_result_wolf_win_when_wolves_dominate(db: Session):
    """
    生存人狼数 >= 生存村側人数 なら WOLF_WIN になること。
    """
    game_id = str(uuid.uuid4())

    # 生存人狼 2
    _add_member(db, game_id, team="WOLF", alive=True, order_no=1, role_type="WEREWOLF")
    _add_member(db, game_id, team="WOLF", alive=True, order_no=2, role_type="WEREWOLF")

    # 生存村人 1
    _add_member(db, game_id, team="VILLAGE", alive=True, order_no=3)

    db.commit()

    result = _judge_game_result(game_id, db)

    assert result["result"] == "WOLF_WIN"
    assert result["wolf_alive"] == 2
    assert result["village_alive"] == 1
    assert result["reason"] == "Wolves are equal to or more than villages."


def test_judge_game_result_ongoing_when_both_sides_alive_and_village_majority(
    db: Session,
):
    """
    生存人狼 > 0 かつ 生存人狼 < 生存村側人数 なら ONGOING になること。
    """
    game_id = str(uuid.uuid4())

    # 生存人狼 1
    _add_member(db, game_id, team="WOLF", alive=True, order_no=1, role_type="WEREWOLF")

    # 生存村人 3
    _add_member(db, game_id, team="VILLAGE", alive=True, order_no=2)
    _add_member(db, game_id, team="VILLAGE", alive=True, order_no=3)
    _add_member(db, game_id, team="VILLAGE", alive=True, order_no=4)

    db.commit()

    result = _judge_game_result(game_id, db)

    assert result["result"] == "ONGOING"
    assert result["wolf_alive"] == 1
    assert result["village_alive"] == 3
    assert result["reason"] == "Game continues."
