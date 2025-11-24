# tests/test_medium.py

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base  # Base は app/db.py で定義されている前提
from app.models.game import Game, GameMember, MediumInspect
from app.api.v1.games import medium_inspect
from fastapi import HTTPException


# -----------------------------
# テスト用の DB セットアップ
# -----------------------------
# メモリ上の SQLite を使用（テストごとにキレイな状態）
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine
)


@pytest.fixture(scope="function")
def db():
    """
    各テストごとに空のDBを作成・破棄するフィクスチャ。
    """
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


# -----------------------------
# ヘルパー: ゲーム&メンバー作成
# -----------------------------
def _create_game_with_medium_and_executed_member(
    db,
    executed_team: str = "WOLF",
):
    """
    テスト用に以下の状態を作るヘルパー:

    - Game:
        - status = "NIGHT"
        - curr_day = 2  (→ 前日 = day_no 1)
        - curr_night = 2
        - last_executed_member_id = 昼に処刑されたメンバー
    - GameMember:
        - medium: role_type = "MEDIUM", team = "VILLAGE", alive = True
        - executed: team = executed_team ("WOLF" or "VILLAGE"), alive = False
    """
    game_id = str(uuid.uuid4())
    medium_id = str(uuid.uuid4())
    executed_id = str(uuid.uuid4())

    game = Game(
        id=game_id,
        room_id="dummy-room",
        status="NIGHT",
        curr_day=2,
        curr_night=2,
        last_executed_member_id=executed_id,
    )

    medium = GameMember(
        id=medium_id,
        game_id=game_id,
        room_member_id="rm-medium",
        display_name="テスト霊媒師",
        avatar_url=None,
        role_type="MEDIUM",
        team="VILLAGE",
        alive=True,
        order_no=1,
    )

    executed = GameMember(
        id=executed_id,
        game_id=game_id,
        room_member_id="rm-executed",
        display_name="前日に処刑された人",
        avatar_url=None,
        role_type="WEREWOLF" if executed_team == "WOLF" else "VILLAGER",
        team=executed_team,  # ★ ここで WOLF/VILLAGE を制御
        alive=False,
        order_no=2,
    )

    db.add(game)
    db.add(medium)
    db.add(executed)
    db.commit()

    return game_id, medium_id, executed_id


# -----------------------------
# 正常系テスト: 処刑者が人狼陣営のとき
# -----------------------------
def test_medium_inspect_returns_wolf_when_executed_is_wolf(db):
    # 準備: 前日に人狼が処刑された状態を作る
    game_id, medium_id, executed_id = _create_game_with_medium_and_executed_member(
        db, executed_team="WOLF"
    )

    # 実行: 霊媒師APIを直接呼び出し
    result = medium_inspect(
        game_id=game_id,
        medium_member_id=medium_id,
        db=db,
    )

    # 検証: レスポンス
    assert result.game_id == game_id
    assert result.medium_member_id == medium_id
    assert result.target_member_id == executed_id
    assert result.day_no == 1  # curr_day=2 のとき、前日=1
    assert result.is_wolf is True

    # DB に MediumInspect が1件作成されていること
    records = db.query(MediumInspect).all()
    assert len(records) == 1
    rec = records[0]
    assert rec.game_id == game_id
    assert rec.medium_member_id == medium_id
    assert rec.target_member_id == executed_id
    assert rec.is_wolf is True


# -----------------------------
# 正常系テスト: 処刑者が村陣営のとき
# -----------------------------
def test_medium_inspect_returns_not_wolf_when_executed_is_village(db):
    # 準備: 前日に村人が処刑された状態
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

    rec = db.query(MediumInspect).one()
    assert rec.is_wolf is False


# -----------------------------
# 異常系テスト: 2回目の霊媒はエラー
# -----------------------------
def test_medium_inspect_twice_same_day_raises_error(db):
    game_id, medium_id, _ = _create_game_with_medium_and_executed_member(
        db, executed_team="WOLF"
    )

    # 1回目は成功
    _ = medium_inspect(
        game_id=game_id,
        medium_member_id=medium_id,
        db=db,
    )

    # 2回目は HTTPException(400) のはず
    with pytest.raises(HTTPException) as exc:
        _ = medium_inspect(
            game_id=game_id,
            medium_member_id=medium_id,
            db=db,
        )

    assert exc.value.status_code == 400
    assert "Medium already inspected" in exc.value.detail
