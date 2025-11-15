# app/schemas/game.py

from pydantic import BaseModel
from typing import Optional, Literal


class GameSettings(BaseModel):
    show_votes_public: bool = True
    day_timer_sec: int = 300

    knight_self_guard: bool = False
    knight_consecutive_guard: bool = False
    allow_no_kill: bool = False

    wolf_vote_lvl1_point: int = 3
    wolf_vote_lvl2_point: int = 2
    wolf_vote_lvl3_point: int = 1


class GameCreate(BaseModel):
    room_id: str
    settings: Optional[GameSettings] = None


class GameOut(BaseModel):
    id: str
    room_id: str
    status: str
    curr_day: int
    curr_night: int

    class Config:
        from_attributes = True


class GameMemberOut(BaseModel):
    id: str
    display_name: str
    avatar_url: Optional[str]
    role_type: Literal["VILLAGER", "WEREWOLF", "SEER", "MEDIUM", "KNIGHT"]
    team: Literal["VILLAGE", "WOLF"]
    alive: bool

    class Config:
        from_attributes = True
