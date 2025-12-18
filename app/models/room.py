# app/models/room.py
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

from ..db import Base


class Room(Base):
    __tablename__ = "rooms"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)

    owner_profile_id = Column(String, ForeignKey("profiles.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # ★追加：現在進行中のゲーム
    current_game_id = Column(String, nullable=True)
    roster = relationship("RoomRoster", back_populates="room", cascade="all, delete-orphan")
    members = relationship("RoomMember", back_populates="room", cascade="all, delete-orphan")


class RoomRoster(Base):
    __tablename__ = "room_roster"

    id = Column(String, primary_key=True)
    room_id = Column(String, ForeignKey("rooms.id"), nullable=False)
    profile_id = Column(String, ForeignKey("profiles.id"), nullable=False)
    alias_name = Column(String, nullable=True)
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    room = relationship("Room", back_populates="roster")


class RoomMember(Base):
    __tablename__ = "room_members"

    id = Column(String, primary_key=True)
    room_id = Column(String, ForeignKey("rooms.id"), nullable=False)
    display_name = Column(String, nullable=False)
    avatar_url = Column(String, nullable=True)
    is_host = Column(Boolean, default=False, nullable=False)  # ★司会フラグ
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    room = relationship("Room", back_populates="members")
