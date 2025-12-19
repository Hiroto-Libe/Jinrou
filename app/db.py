# app/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite:///./werewolf.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite用
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def ensure_room_members_schema() -> None:
    """
    SQLite では Base.metadata.create_all() では既存テーブルに列が追加されない。
    司会フラグ（is_host）が欠落している既存 DB を自動でアップグレードする。
    """
    with engine.begin() as conn:
        result = conn.exec_driver_sql("PRAGMA table_info(room_members)")
        columns = {row[1] for row in result.fetchall()}
        if not columns:
            # テーブル未作成（create_all 前）か、まだゲーム機能未使用
            return
        if "is_host" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE room_members "
                "ADD COLUMN is_host BOOLEAN NOT NULL DEFAULT 0"
            )
