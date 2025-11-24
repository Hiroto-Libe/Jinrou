# app/schemas/knight.py
from pydantic import BaseModel
from datetime import datetime


class KnightGuardCreate(BaseModel):
    """騎士の護衛リクエスト"""
    target_member_id: str


class KnightGuardOut(BaseModel):
    """騎士の護衛結果（記録情報）"""
    id: str
    game_id: str
    night_no: int
    knight_member_id: str
    target_member_id: str
    created_at: datetime

    class Config:
        from_attributes = True
