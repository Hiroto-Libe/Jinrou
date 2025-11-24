# app/schemas/medium.py
from pydantic import BaseModel

class MediumInspectOut(BaseModel):
    id: str
    game_id: str
    day_no: int
    medium_member_id: str
    target_member_id: str
    is_wolf: bool

    class Config:
        orm_mode = True
