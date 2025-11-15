# app/api/deps.py
from ..db import SessionLocal
from sqlalchemy.orm import Session


def get_db_dep():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
