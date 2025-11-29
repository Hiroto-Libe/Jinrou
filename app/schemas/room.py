# app/schemas/room.py
from pydantic import BaseModel, ConfigDict
from typing import Optional

class RoomRosterJoinRequest(BaseModel):
    display_name: str

    model_config = ConfigDict(from_attributes=True)
    
class RoomCreate(BaseModel):
    name: str
    owner_profile_id: Optional[str] = None


class RoomOut(BaseModel):
    id: str
    name: str

    class Config:
        from_attributes = True


# --- roster / members 用 ---

class RoomRosterCreate(BaseModel):
    profile_id: str
    alias_name: Optional[str] = None


class RoomRosterItem(BaseModel):
    id: str
    profile_id: str
    display_name: str
    alias_name: Optional[str]
    avatar_url: Optional[str]

    class Config:
        from_attributes = True


class RoomMemberListItem(BaseModel):
    id: str
    display_name: str
    avatar_url: Optional[str]

    class Config:
        from_attributes = True


class BulkMembersFromRosterRequest(BaseModel):
    profile_ids: list[str]
