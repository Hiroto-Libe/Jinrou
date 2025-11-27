import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app.models.game import GameMember, Game
from app.api.v1.games import medium_inspect


# -----------------------------
# テスト補助関数
# -----------------------------
def _create_game_with_medium_and_executed_member(db, executed_team):
    """
    テスト用のゲーム/霊媒師/前日の処刑者を作成する。
    executed_team: "WOLF" または "VILLAGE"
    """
    # ゲーム作成
    game = Game(
        id="game1",
        room_id="room1",
        status="NIGHT",
        curr_day=2,
        curr_night=2,
        last_executed_member_id="executed1",
    )
    db.add(game)
    db.commit()

    # 霊媒師（生存中）
    medium = GameMember(
        id="medium1",
        game_id="game1",
        room_member_id="rm1",
        display_name="霊媒師",
        avatar_url=None,
        role_type="MEDIUM",
        team="VILLAGE",
        alive=True,
        order_no=1,
    )
    db.add(medium)

    # 前日に処刑されたプレイヤー
    executed = GameMember(
        id="executed1",
        game_id="game1",
        room_member_id="rm2",
        display_name="処刑者",
        avatar_url=None,
        role_type=("WEREWOLF" if executed_team == "WOLF" else "VILLAGER"),
        team=executed_team,
        alive=False,
        order_no=2,
    )
    db.add(executed)

    db.commit()

    return game.id, medium.id, executed.id


# -----------------------------
# ❶ executed が WOLF → 黒判定
# -----------------------------
def test_medium_inspect_returns_wolf_when_executed_is_wolf(db):
    # 準備
    game_id, medium_id, executed_id = _create_game_with_medium_and_executed_member(
        db, executed_team="WOLF"
    )

    # 実行
    result = medium_inspect(
        game_id=game_id,
        medium_member_id=medium_id,
        db=db,
    )

    # 検証
    assert result.is_wolf is True
    assert result.target_member_id == executed_id


# -----------------------------
# ❷ executed が VILLAGE → 白判定
# -----------------------------
def test_medium_inspect_returns_not_wolf_when_executed_is_village(db):
    # 準備
    game_id, medium_id, executed_id = _create_game_with_medium_and_executed_member(
        db, executed_team="VILLAGE"
    )

    # 実行
    result = medium_inspect(
        game_id=game_id,
        medium_member_id=medium_id,
        db=db,
    )

    # 検証
    assert result.is_wolf is False
    assert result.target_member_id == executed_id


# -----------------------------
# ❸ 同じ day_no で 2回使うとエラー
# -----------------------------
def test_medium_inspect_twice_same_day_raises_error(db):
    # 準備
    game_id, medium_id, _ = _create_game_with_medium_and_executed_member(
        db, executed_team="WOLF"
    )

    # 1回目（成功）
    _ = medium_inspect(
        game_id=game_id,
        medium_member_id=medium_id,
        db=db,
    )

    # 2回目 → エラー
    with pytest.raises(Exception):
        _ = medium_inspect(
            game_id=game_id,
            medium_member_id=medium_id,
            db=db,
        )
