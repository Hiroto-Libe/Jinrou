# tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db import Base

# テスト用 SQLite メモリDB
TEST_DATABASE_URL = "sqlite:///:memory:"

# Engine と SessionLocal をテスト専用に構築
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

@pytest.fixture(scope="function")
def db():
    """
    すべてのテストで共通して利用するテスト用 DB セッション。
    テストごとに:
      1. テーブルを create_all で構築
      2. セッションを yield で渡す
      3. テスト終了後に drop_all で完全削除してクリーン化
    """
    # テストごとに完全な空DBを作成
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # テーブルを完全削除（次のテストをまっさらにする）
        Base.metadata.drop_all(bind=engine)
