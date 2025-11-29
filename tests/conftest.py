# tests/conftest.py
import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.db import Base, engine, SessionLocal
from app.main import app

# Room を Base に登録しておく（他のモデルも __init__ 経由で import 済みなら不要）
from app.models.room import Room  # noqa: F401


@pytest.fixture(scope="function")
def db() -> Session:
    """
    テストごとにクリーンな DB を用意するフィクスチャ。
    アプリ本体と同じ engine を使う。
    """
    # 既存テーブルを全部削除してから、再作成
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client() -> TestClient:
    """
    通常の FastAPI app をそのまま使う TestClient。
    DI の上書きは行わない。
    """
    with TestClient(app) as c:
        yield c
