import uuid
import pytest
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.game import Game, GameMember
from app.api.v1.games import seer_inspect
from app.schemas.seer import SeerInspectCreate


# -----------------------------
# ヘルパー：ゲーム＋占い師＋ターゲット作成
# -----------------------------
def _create_game_with_seer_and_target(
    db: Session,
    target_role: str,
    target_team: str,
    target_alive: bool = True,
):
    """
    占い師APIテスト用の共通セットアップ。

    - status="NIGHT"
    - curr_night=1
    - 占い師(SEER) 1人（生存）
    - ターゲット1人（role/team/生死は引数で指定）
    """
    game = Game(
        id=str(uuid.uuid4()),
        room_id=str(uuid.uuid4()),
        status="NIGHT",
        curr_day=1,
        curr_night=1,
    )
    db.add(game)
    db.commit()
    db.refresh(game)

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

    target = GameMember(
        id=str(uuid.uuid4()),
        game_id=game.id,
        room_member_id=str(uuid.uuid4()),
        display_name="Target",
        avatar_url=None,
        role_type=target_role,
        team=target_team,
        alive=target_alive,
        order_no=2,
    )

    db.add_all([seer, target])
    db.commit()
    db.refresh(seer)
    db.refresh(target)

    return game, seer, target


# -----------------------------
# ❶ 人狼を占ったら黒になる
# -----------------------------
def test_seer_inspect_returns_wolf_for_werewolf_target(db: Session):
    game, seer, wolf = _create_game_with_seer_and_target(
        db,
        target_role="WEREWOLF",
        target_team="WOLF",
        target_alive=True,
    )

    data = SeerInspectCreate(target_member_id=wolf.id)

    result = seer_inspect(
        game_id=game.id,
        seer_member_id=seer.id,
        data=data,
        db=db,
    )

    assert result.game_id == game.id
    assert result.seer_member_id == seer.id
    assert result.target_member_id == wolf.id
    assert result.is_wolf is True


# -----------------------------
# ❷ 村人を占ったら白になる
# -----------------------------
def test_seer_inspect_returns_not_wolf_for_villager_target(db: Session):
    game, seer, villager = _create_game_with_seer_and_target(
        db,
        target_role="VILLAGER",
        target_team="VILLAGE",
        target_alive=True,
    )

    data = SeerInspectCreate(target_member_id=villager.id)

    result = seer_inspect(
        game_id=game.id,
        seer_member_id=seer.id,
        data=data,
        db=db,
    )

    assert result.is_wolf is False
    assert result.target_member_id == villager.id


# -----------------------------
# ❸ 狂人(MADMAN)は白になる
#     ※ 狂人は team="WOLF" だが、判定ロジック上は白
# -----------------------------
def test_seer_inspect_returns_not_wolf_for_madman_target(db: Session):
    game, seer, madman = _create_game_with_seer_and_target(
        db,
        target_role="MADMAN",
        target_team="WOLF",
        target_alive=True,
    )

    data = SeerInspectCreate(target_member_id=madman.id)

    result = seer_inspect(
        game_id=game.id,
        seer_member_id=seer.id,
        data=data,
        db=db,
    )

    # role_type が WEREWOLF のときだけ黒 → MADMAN は白
    assert result.is_wolf is False
    assert result.target_member_id == madman.id


# -----------------------------
# ❹ 同じ夜に2回占うとエラーになる
# -----------------------------
def test_seer_inspect_twice_same_night_raises_error(db: Session):
    game, seer, villager = _create_game_with_seer_and_target(
        db,
        target_role="VILLAGER",
        target_team="VILLAGE",
        target_alive=True,
    )

    data = SeerInspectCreate(target_member_id=villager.id)

    # 1回目は成功
    _ = seer_inspect(
        game_id=game.id,
        seer_member_id=seer.id,
        data=data,
        db=db,
    )

    # 2回目 → HTTPException(400) の想定
    with pytest.raises(HTTPException) as excinfo:
        _ = seer_inspect(
            game_id=game.id,
            seer_member_id=seer.id,
            data=data,
            db=db,
        )

    assert excinfo.value.status_code == 400
    assert "already inspected" in excinfo.value.detail


# -----------------------------
# ❺ ゲームが NIGHT 以外だとエラー
# -----------------------------
def test_seer_inspect_fails_if_game_not_night(db: Session):
    game, seer, villager = _create_game_with_seer_and_target(
        db,
        target_role="VILLAGER",
        target_team="VILLAGE",
        target_alive=True,
    )

    # 状態を DAY_DISCUSSION に変更
    game.status = "DAY_DISCUSSION"
    db.add(game)
    db.commit()
    db.refresh(game)

    data = SeerInspectCreate(target_member_id=villager.id)

    with pytest.raises(HTTPException) as excinfo:
        _ = seer_inspect(
            game_id=game.id,
            seer_member_id=seer.id,
            data=data,
            db=db,
        )

    assert excinfo.value.status_code == 400
    assert "not in NIGHT" in excinfo.value.detail


# -----------------------------
# ❻ 死亡しているプレイヤーは占えない
# -----------------------------
def test_seer_inspect_fails_if_target_dead(db: Session):
    game, seer, dead_villager = _create_game_with_seer_and_target(
        db,
        target_role="VILLAGER",
        target_team="VILLAGE",
        target_alive=False,  # 死亡
    )

    data = SeerInspectCreate(target_member_id=dead_villager.id)

    with pytest.raises(HTTPException) as excinfo:
        _ = seer_inspect(
            game_id=game.id,
            seer_member_id=seer.id,
            data=data,
            db=db,
        )

    assert excinfo.value.status_code == 400
    assert "already dead" in excinfo.value.detail.lower()
