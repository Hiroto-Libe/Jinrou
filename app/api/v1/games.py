# app/api/v1/games.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
import uuid
from typing import List

from ...api.deps import get_db_dep
from ...models.room import RoomMember
from ...models.game import Game, GameMember, WolfVote
from ...schemas.game import GameCreate, GameOut, GameMemberOut
from ...schemas.night import WolfVoteCreate, WolfVoteOut, WolfTallyItem, WolfTallyOut

router = APIRouter(prefix="/games", tags=["games"])

# （create_game, assign_roles, get_game はすでにある想定）


# -----------------------------
# 🐺 夜の人狼投票
# -----------------------------
@router.post("/{game_id}/wolves/vote", response_model=WolfVoteOut)
def wolf_vote(
    game_id: str,
    data: WolfVoteCreate,
    db: Session = Depends(get_db_dep),
):
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if game.status != "NIGHT":
        raise HTTPException(status_code=400, detail="Game is not in NIGHT phase")

    # 人狼本人の GameMember を確認
    wolf = db.get(GameMember, data.wolf_member_id)
    if not wolf or wolf.game_id != game_id:
        raise HTTPException(status_code=404, detail="Wolf member not found")

    if wolf.team != "WOLF" or wolf.role_type != "WEREWOLF":
        raise HTTPException(status_code=400, detail="Member is not a werewolf")

    if not wolf.alive:
        raise HTTPException(status_code=400, detail="Dead wolf cannot vote")

    # ターゲットの GameMember を確認
    target = db.get(GameMember, data.target_member_id)
    if not target or target.game_id != game_id:
        raise HTTPException(status_code=404, detail="Target member not found")

    if not target.alive:
        raise HTTPException(status_code=400, detail="Target is already dead")

    if target.id == wolf.id:
        raise HTTPException(status_code=400, detail="Wolf cannot target themselves")

    if target.team == "WOLF":
        raise HTTPException(status_code=400, detail="Wolf cannot target other wolves")

    # priority_level → ポイント値
    if data.priority_level == 1:
        pts = game.wolf_vote_lvl1_point
    elif data.priority_level == 2:
        pts = game.wolf_vote_lvl2_point
    else:
        pts = game.wolf_vote_lvl3_point

    night_no = game.curr_night

    # 既存投票があれば上書き（UPSERT的挙動）
    existing: WolfVote | None = (
        db.query(WolfVote)
        .filter(
            WolfVote.game_id == game_id,
            WolfVote.night_no == night_no,
            WolfVote.wolf_member_id == wolf.id,
        )
        .one_or_none()
    )

    if existing:
        existing.target_member_id = target.id
        existing.priority_level = data.priority_level
        existing.points_at_vote = pts
        vote = existing
    else:
        vote = WolfVote(
            id=str(uuid.uuid4()),
            game_id=game_id,
            night_no=night_no,
            wolf_member_id=wolf.id,
            target_member_id=target.id,
            priority_level=data.priority_level,
            points_at_vote=pts,
        )
        db.add(vote)

    db.commit()
    db.refresh(vote)
    return WolfVoteOut.model_validate(vote)


# -----------------------------
# 🧮 夜の人狼投票 集計
# -----------------------------
@router.get("/{game_id}/wolves/tally", response_model=WolfTallyOut)
def wolf_tally(
    game_id: str,
    night_no: int | None = None,
    db: Session = Depends(get_db_dep),
):
    """
    ある夜の人狼投票集計を取得する。
    night_no を省略した場合は game.curr_night を使う。
    """
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if night_no is None:
        night_no = game.curr_night

    # targetごとのポイント合計と票数
    rows = (
        db.query(
            WolfVote.target_member_id,
            func.sum(WolfVote.points_at_vote).label("total_points"),
            func.count().label("vote_count"),
        )
        .filter(
            WolfVote.game_id == game_id,
            WolfVote.night_no == night_no,
        )
        .group_by(WolfVote.target_member_id)
        .all()
    )

    items = [
        WolfTallyItem(
            target_member_id=target_member_id,
            total_points=int(total_points),
            vote_count=int(vote_count),
        )
        for target_member_id, total_points, vote_count in rows
    ]

    return WolfTallyOut(
        game_id=game_id,
        night_no=night_no,
        items=items,
    )
