# app/api/v1/endpoints/games_me.py みたいなファイルを作る想定
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db  # 実際のパスに合わせて
from app.models import GameMember  # 実際のモデルに合わせて
from app.schemas.game_member import GameMemberMe

router = APIRouter(prefix="/games", tags=["games"])


@router.get("/{game_id}/me", response_model=GameMemberMe)
def get_my_info(game_id: str, player_id: str, db: Session = Depends(get_db)):
    member = (
        db.query(GameMember)
        .filter(
            GameMember.game_id == game_id,
            GameMember.player_id == player_id,
        )
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="Player not found in this game")

    return GameMemberMe(
        game_id=member.game_id,
        player_id=member.player_id,
        role=member.role,      # 文字列前提
        status=member.status,  # alive / dead
    )
