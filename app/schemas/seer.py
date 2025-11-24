# app/schemas/seer.py
from pydantic import BaseModel
from datetime import datetime


class SeerFirstWhiteOut(BaseModel):
    """初日白通知のレスポンス"""
    game_id: str
    seer_member_id: str
    target_member_id: str
    target_display_name: str
    is_wolf: bool  # 常に False（人狼ではないことを通知）

    class Config:
        from_attributes = True


class SeerInspectCreate(BaseModel):
    """占い師が夜に占うときのリクエスト"""
    target_member_id: str


class SeerInspectOut(BaseModel):
    """占い結果の保存内容"""
    id: str
    game_id: str
    night_no: int
    seer_member_id: str
    target_member_id: str
    is_wolf: bool
    created_at: datetime

    class Config:
        from_attributes = True
