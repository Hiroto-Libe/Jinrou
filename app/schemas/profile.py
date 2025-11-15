# app/schemas/profile.py

from pydantic import BaseModel
from typing import Optional


class ProfileBase(BaseModel):
    display_name: str
    avatar_url: Optional[str] = None
    note: Optional[str] = None


class ProfileCreate(ProfileBase):
    """POST /api/profiles 用"""
    pass


class ProfileOut(ProfileBase):
    """レスポンス用"""
    id: str
    is_deleted: bool

    class Config:
        from_attributes = True
