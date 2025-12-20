# app/schemas/night.py

from pydantic import BaseModel, ConfigDict
from typing import Literal


class WolfVoteCreate(BaseModel):
    """人狼が夜に投票する際のリクエストボディ"""
    wolf_member_id: str
    target_member_id: str
    priority_level: Literal[1, 2, 3]

class WolfVoteIn(BaseModel):
    wolf_member_id: str
    target_member_id: str
    priority_level: int = 1

class WolfVoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    game_id: str
    night_no: int
    wolf_member_id: str
    target_member_id: str
    priority_level: int


class WolfTallyItem(BaseModel):
    """集計結果の1ターゲット分"""
    target_member_id: str
    total_points: int
    vote_count: int


class WolfTallyOut(BaseModel):
    """その夜の人狼投票の集計結果"""
    game_id: str
    night_no: int
    items: list[WolfTallyItem]


class NightActionsStatusOut(BaseModel):
    """夜行動の進捗（司会向け）"""
    game_id: str
    night_no: int
    wolves_total: int
    wolves_done: int
    seer_total: int
    seer_done: int
    knight_total: int
    knight_done: int
    all_done: bool
