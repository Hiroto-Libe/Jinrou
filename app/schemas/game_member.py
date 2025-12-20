# app/schemas/game_member_me.py （ファイル名はお好みで）
from pydantic import BaseModel

class GameMemberMe(BaseModel):
    game_id: str
    player_id: str
    role: str    # "villager", "seer", "knight", "wolf", "madman" など
    status: str  # "alive" / "dead"
    is_host: bool = False
