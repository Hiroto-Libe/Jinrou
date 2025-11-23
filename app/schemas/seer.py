# app/schemas/seer.py

from pydantic import BaseModel

class SeerFirstWhiteOut(BaseModel):
    game_id: str
    seer_member_id: str
    target_member_id: str
    target_display_name: str
    is_wolf: bool = False  # 常に False（＝人狼ではない）

    class Config:
        from_attributes = True
