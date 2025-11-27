# tests/test_madman_behavior.py

import uuid
from sqlalchemy.orm import Session

from app.models.game import Game, GameMember
from app.api.v1.games import (
    seer_inspect,
    medium_inspect,
    _judge_game_result,  # 勝敗判定のヘルパーを直接使う
)
from app.schemas.seer import SeerInspectCreate


def _create_base_game(db: Session, status: str = "NIGHT") -> Game:
    """共通で使う Game を1つ作るだけのヘルパー。"""
    game = Game(
        id=str(uuid.uuid4()),
        room_id=str(uuid.uuid4()),
        status=status,
        curr_day=2,     # 霊媒テストで「前日」が 1日目になるように
        curr_night=2,
    )
    db.add(game)
    db.commit()
    db.refresh(game)
    return game


# 1) 占い師が狂人を占ったとき、白になることを確認
def test_seer_inspect_madman_is_white(db: Session):
    game = _create_base_game(db, status="NIGHT")

    # 占い師
    seer = GameMember(
        id=str(uuid.uuid4()),
        game_id=game.id,
        room_member_id=str(uuid.uuid4()),
        display_name="Seer",
        avatar_url=None,
        role_type="SEER",
        team="VILLAGE",
        alive=True,
        order_no=1,
    )

    # 狂人（MADMAN）：team は WOLF だが、判定上は白にしたい
    madman = GameMember(
        id=str(uuid.uuid4()),
        game_id=game.id,
        room_member_id=str(uuid.uuid4()),
        display_name="Madman",
        avatar_url=None,
        role_type="MADMAN",
        team="WOLF",
        alive=True,
        order_no=2,
    )

    db.add_all([seer, madman])
    db.commit()
    db.refresh(seer)
    db.refresh(madman)

    data = SeerInspectCreate(target_member_id=madman.id)

    result = seer_inspect(
        game_id=game.id,
        seer_member_id=seer.id,
        data=data,
        db=db,
    )

    # 狂人は「白」と判定される想定
    assert result.is_wolf is False


# 2) 霊媒師が「前日に処刑された狂人」を見たとき、白になることを確認
def test_medium_inspect_madman_is_white(db: Session):
    game = _create_base_game(db, status="NIGHT")

    # 霊媒師
    medium = GameMember(
        id=str(uuid.uuid4()),
        game_id=game.id,
        room_member_id=str(uuid.uuid4()),
        display_name="Medium",
        avatar_url=None,
        role_type="MEDIUM",
        team="VILLAGE",
        alive=True,
        order_no=1,
    )

    # 前日に処刑された狂人（alive=False）
    executed_madman = GameMember(
        id=str(uuid.uuid4()),
        game_id=game.id,
        room_member_id=str(uuid.uuid4()),
        display_name="Executed Madman",
        avatar_url=None,
        role_type="MADMAN",
        team="WOLF",
        alive=False,
        order_no=2,
    )

    db.add_all([medium, executed_madman])
    db.commit()
    db.refresh(medium)
    db.refresh(executed_madman)

    # Game 側に「直前の昼に処刑されたプレイヤー」を紐付け
    game.last_executed_member_id = executed_madman.id
    db.add(game)
    db.commit()
    db.refresh(game)

    result = medium_inspect(
        game_id=game.id,
        medium_member_id=medium.id,
        db=db,
    )

    # 狂人は「白」と判定される想定
    assert result.is_wolf is False
    assert result.target_member_id == executed_madman.id


# 3) 勝利判定では狂人も狼陣営として数えられることの確認
def test_judge_counts_madman_as_wolf_side(db: Session):
    game = _create_base_game(db, status="DAY_DISCUSSION")

    # 生存村人 1人
    villager = GameMember(
        id=str(uuid.uuid4()),
        game_id=game.id,
        room_member_id=str(uuid.uuid4()),
        display_name="Villager",
        avatar_url=None,
        role_type="VILLAGER",
        team="VILLAGE",
        alive=True,
        order_no=1,
    )

    # 死んだ人狼 1人（カウントされない想定）
    dead_wolf = GameMember(
        id=str(uuid.uuid4()),
        game_id=game.id,
        room_member_id=str(uuid.uuid4()),
        display_name="Dead Wolf",
        avatar_url=None,
        role_type="WEREWOLF",
        team="WOLF",
        alive=False,
        order_no=2,
    )

    # 生存狂人 1人（勝敗判定では狼サイドとしてカウントしたい）
    madman = GameMember(
        id=str(uuid.uuid4()),
        game_id=game.id,
        room_member_id=str(uuid.uuid4()),
        display_name="Madman",
        avatar_url=None,
        role_type="MADMAN",
        team="WOLF",
        alive=True,
        order_no=3,
    )

    db.add_all([villager, dead_wolf, madman])
    db.commit()

    result = _judge_game_result(game.id, db)

    # 生存: 村1 / 狼陣営1（狂人のみ） → 狼数 >= 村数 → WOLF_WIN になる想定
    assert result["wolf_alive"] == 1
    assert result["village_alive"] == 1
    assert result["result"] == "WOLF_WIN"
