# app/api/deps.py

from collections.abc import Generator
from sqlalchemy.orm import Session

from app.db import SessionLocal  # ★ 既存の db.py で SessionLocal を定義している前提

def get_db_dep() -> Generator[Session, None, None]:
    """
    FastAPI の Depends で使う DB セッション依存関数。
    エンドポイント側では `db: Session = Depends(get_db)` で利用。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 新しく追加したエンドポイント用に、別名も用意しておく
# これで from app.api.deps import get_db も動く
get_db = get_db_dep