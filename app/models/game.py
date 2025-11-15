# app/models/game.py
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from ..db import Base


class Game(Base):
    __tablename__ = "games"

    id = Column(String, primary_key=True)
    room_id = Column(String, ForeignKey("rooms.id"), nullable=False)

    status = Column(String, nullable=False, default="WAITING")
    curr_day = Column(Integer, nullable=False, default=1)
    curr_night = Column(Integer, nullable=False, default=1)
    vote_round = Column(Integer, nullable=False, default=0)
    tie_streak = Column(Integer, nullable=False, default=0)

    show_votes_public = Column(Boolean, nullable=False, default=True)
    day_timer_sec = Column(Integer, nullable=False, default=300)

    knight_self_guard = Column(Boolean, nullable=False, default=False)
    knight_consecutive_guard = Column(Boolean, nullable=False, default=False)
    allow_no_kill = Column(Boolean, nullable=False, default=False)

    wolf_vote_lvl1_point = Column(Integer, nullable=False, default=3)
    wolf_vote_lvl2_point = Column(Integer, nullable=False, default=2)
    wolf_vote_lvl3_point = Column(Integer, nullable=False, default=1)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)

    members = relationship("GameMember", back_populates="game", cascade="all, delete-orphan")


class GameMember(Base):
    __tablename__ = "game_members"

    id = Column(String, primary_key=True)
    game_id = Column(String, ForeignKey("games.id"), nullable=False)
    room_member_id = Column(String, ForeignKey("room_members.id"), nullable=False)

    display_name = Column(String, nullable=False)
    avatar_url = Column(String, nullable=True)

    role_type = Column(String, nullable=False)  # 'VILLAGER','WEREWOLF','SEER','MEDIUM','KNIGHT'
    team = Column(String, nullable=False)       # 'VILLAGE' or 'WOLF'

    alive = Column(Boolean, nullable=False, default=True)
    order_no = Column(Integer, nullable=False, default=0)

    game = relationship("Game", back_populates="members")
