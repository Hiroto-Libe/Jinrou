import uuid
import pytest
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.game import Game, GameMember
from app.models.knight import KnightGuard
from app.api.v1.games import knight_guard
from app.schemas.knight import KnightGuardCreate


# -----------------------------
# 共通セットアップ
# -----------------------------
def _create_game_with_knight_and_target(
    db: Session,
    *,
    knight_self_guard: bool = False,
    knight_consecutive_guard: bool = False,
    status: str = "NIGHT",
    curr_night: int = 1,
):
    """
    騎士APIテスト用の共通セットアップ。

    - Game 1件
    - KNIGHT 1人（生存）
    - 対象プレイヤー 1人（村人・生存）
    """
    game = Game(
        id=str(uuid.uuid4()),
        room_id=str(uuid.uuid4()),
        status=status,
        curr_day=1,
        curr_night=curr_night,
        knight_self_guard=knight_self_guard,
        knight_consecutive_guard=knight_consecutive_guard,
    )
    db.add(game)
    db.commit()
    db.refresh(game)

    knight = GameMember(
        id=str(uuid.uuid4()),
        game_id=game.id,
        room_member_id=str(uuid.uuid4()),
        display_name="Knight",
        avatar_url=None,
        role_type="KNIGHT",
        team="VILLAGE",
        alive=True,
        order_no=1,
    )

    target = GameMember(
        id=str(uuid.uuid4()),
        game_id=game.id,
        room_member_id=str(uuid.uuid4()),
        display_name="Target",
        avatar_url=None,
        role_type="VILLAGER",
        team="VILLAGE",
        alive=True,
        order_no=2,
    )

    db.add_all([knight, target])
    db.commit()
    db.refresh(knight)
    db.refresh(target)

    return game, knight, target


# -----------------------------
# ❶ 通常パターン: 他人を護衛 → 成功
# -----------------------------
def test_knight_guard_success_other_player(db: Session):
    game, knight, target = _create_game_with_knight_and_target(
        db,
        knight_self_guard=False,
        knight_consecutive_guard=False,
    )

    data = KnightGuardCreate(target_member_id=target.id)

    result = knight_guard(
        game_id=game.id,
        knight_member_id=knight.id,
        data=data,
        db=db,
    )

    assert result.game_id == game.id
    assert result.knight_member_id == knight.id
    assert result.target_member_id == target.id
    assert result.night_no == game.curr_night

    # DBに1件だけレコードができていることも確認
    guards = db.query(KnightGuard).filter_by(game_id=game.id).all()
    assert len(guards) == 1


# -----------------------------
# ❷ self_guard が False のとき、自己護衛はエラー
# -----------------------------
def test_knight_guard_self_guard_not_allowed(db: Session):
    game, knight, _ = _create_game_with_knight_and_target(
        db,
        knight_self_guard=False,   # 自己護衛禁止
        knight_consecutive_guard=False,
    )

    data = KnightGuardCreate(target_member_id=knight.id)

    with pytest.raises(HTTPException) as excinfo:
        _ = knight_guard(
            game_id=game.id,
            knight_member_id=knight.id,
            data=data,
            db=db,
        )

    assert excinfo.value.status_code == 400
    assert "Self guard is not allowed" in excinfo.value.detail


# -----------------------------
# ❸ self_guard が True のとき、自己護衛は成功
# -----------------------------
def test_knight_guard_self_guard_allowed(db: Session):
    game, knight, _ = _create_game_with_knight_and_target(
        db,
        knight_self_guard=True,    # 自己護衛許可
        knight_consecutive_guard=False,
    )

    data = KnightGuardCreate(target_member_id=knight.id)

    result = knight_guard(
        game_id=game.id,
        knight_member_id=knight.id,
        data=data,
        db=db,
    )

    assert result.game_id == game.id
    assert result.knight_member_id == knight.id
    assert result.target_member_id == knight.id


# -----------------------------
# ❹ 連続護衛禁止: 前夜と同じ対象を守ろうとするとエラー
# -----------------------------
def test_knight_guard_consecutive_guard_not_allowed(db: Session):
    # night=1 で1回目、night=2 で2回目を試す
    game, knight, target = _create_game_with_knight_and_target(
        db,
        knight_self_guard=True,
        knight_consecutive_guard=False,  # 連続護衛禁止
        curr_night=1,
    )

    data = KnightGuardCreate(target_member_id=target.id)

    # 1回目（night=1）は成功
    _ = knight_guard(
        game_id=game.id,
        knight_member_id=knight.id,
        data=data,
        db=db,
    )

    # night を進める
    game.curr_night = 2
    db.add(game)
    db.commit()
    db.refresh(game)

    # 2回目（night=2）に同じ対象を守ろうとするとエラー
    with pytest.raises(HTTPException) as excinfo:
        _ = knight_guard(
            game_id=game.id,
            knight_member_id=knight.id,
            data=data,
            db=db,
        )

    assert excinfo.value.status_code == 400
    assert "Consecutive guard is not allowed" in excinfo.value.detail


# -----------------------------
# ❺ 同じ夜に2回護衛しようとするとエラー
# -----------------------------
def test_knight_guard_twice_same_night_raises_error(db: Session):
    game, knight, target = _create_game_with_knight_and_target(
        db,
        knight_self_guard=True,
        knight_consecutive_guard=True,
        curr_night=1,
    )

    data = KnightGuardCreate(target_member_id=target.id)

    # 1回目は成功
    _ = knight_guard(
        game_id=game.id,
        knight_member_id=knight.id,
        data=data,
        db=db,
    )

    # 同じ night_no で2回目 → エラー
    with pytest.raises(HTTPException) as excinfo:
        _ = knight_guard(
            game_id=game.id,
            knight_member_id=knight.id,
            data=data,
            db=db,
        )

    assert excinfo.value.status_code == 400
    assert "already guarded" in excinfo.value.detail


# -----------------------------
# ❻ ゲームが NIGHT 以外だとエラー
# -----------------------------
def test_knight_guard_fails_if_not_night(db: Session):
    game, knight, target = _create_game_with_knight_and_target(
        db,
        knight_self_guard=False,
        knight_consecutive_guard=False,
        status="DAY_DISCUSSION",   # 夜ではない
    )

    data = KnightGuardCreate(target_member_id=target.id)

    with pytest.raises(HTTPException) as excinfo:
        _ = knight_guard(
            game_id=game.id,
            knight_member_id=knight.id,
            data=data,
            db=db,
        )

    assert excinfo.value.status_code == 400
    assert "not in NIGHT phase" in excinfo.value.detail
