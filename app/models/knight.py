from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)

from app.db import Base  # プロジェクトの他モデルと合わせてください


class KnightGuard(Base):
    __tablename__ = "knight_guards"

    id = Column(String, primary_key=True, index=True)

    # どのゲームの護衛か
    game_id = Column(String, ForeignKey("games.id"), nullable=False, index=True)

    # 何日目（何夜目）の護衛か
    night_no = Column(Integer, nullable=False)

    # 守った騎士（GameMember）
    knight_member_id = Column(String, ForeignKey("game_members.id"), nullable=False)

    # 護衛対象（GameMember）
    target_member_id = Column(String, ForeignKey("game_members.id"), nullable=False)

    # 成功/失敗フラグ（使わないなら削ってもOK）
    guarded_success = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 同じ騎士が同じ夜に複数 guard できないようにする制約
    __table_args__ = (
        UniqueConstraint(
            "game_id", "night_no", "knight_member_id",
            name="uq_knight_guard_once_per_night",
        ),
    )
