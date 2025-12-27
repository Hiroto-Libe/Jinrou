# app/api/v1/debug.py

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
import uuid

from ...api.deps import get_db_dep
from ...db import Base, engine, ensure_room_members_schema
from ...models.room import Room, RoomRoster, RoomMember
from ...models.profile import Profile
from ...models.game import Game, GameMember, DayVote, WolfVote, SeerInspect
from ...models.knight import KnightGuard
from ...schemas.game import GameCreate
from .games import create_game, start_game

router = APIRouter(prefix="/debug", tags=["debug"])


class DebugSeedRequest(BaseModel):
    room_name: str | None = None
    player_names: list[str] | None = None
    player_count: int | None = None
    start_game: bool = True


class DebugGameMemberUpdate(BaseModel):
    member_id: str
    role_type: str | None = None
    team: str | None = None
    alive: bool | None = None


class DebugSetGameMembersRequest(BaseModel):
    game_id: str
    updates: list[DebugGameMemberUpdate]
    reset_votes: bool = True


@router.post("/reset_and_seed")
def reset_and_seed(
    data: DebugSeedRequest,
    db: Session = Depends(get_db_dep),
):
    # DB 全消し（開発専用）
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    ensure_room_members_schema()

    # 参加者名を決定
    if data.player_names:
        names = data.player_names
    else:
        count = data.player_count or 6
        names = [f"Player{i+1}" for i in range(count)]

    # Room 作成
    room = Room(
        id=str(uuid.uuid4()),
        name=data.room_name or "Debug Room",
        owner_profile_id=None,
    )
    db.add(room)
    db.flush()

    # roster と members を作成
    roster_items = []
    for idx, name in enumerate(names):
        profile = Profile(
            id=str(uuid.uuid4()),
            display_name=name,
            avatar_url=None,
            is_deleted=False,
        )
        db.add(profile)
        db.flush()

        roster = RoomRoster(
            id=str(uuid.uuid4()),
            room_id=room.id,
            profile_id=profile.id,
            alias_name=None,
        )
        db.add(roster)
        roster_items.append(
            {
                "id": roster.id,
                "profile_id": profile.id,
                "display_name": name,
                "alias_name": None,
                "avatar_url": None,
            }
        )

        member = RoomMember(
            id=str(uuid.uuid4()),
            room_id=room.id,
            display_name=name,
            avatar_url=None,
            is_host=(idx == 0),
        )
        db.add(member)

    db.commit()

    game_id = None
    if data.start_game:
        game = create_game(GameCreate(room_id=room.id), db)
        game_id = game.id
        start_game(game_id, payload=None, db=db)

    # GameMembers を返す（start_game 後に作成済みの想定）
    members = (
        db.query(GameMember)
        .filter(GameMember.game_id == game_id)
        .order_by(GameMember.order_no.asc())
        .all()
        if game_id
        else []
    )

    game_members = [
        {
            "id": m.id,
            "display_name": m.display_name,
            "role_type": m.role_type,
            "team": m.team,
        }
        for m in members
    ]

    return {
        "room_id": room.id,
        "game_id": game_id,
        "roster": roster_items,
        "game_members": game_members,
    }


@router.post("/set_game_members")
def set_game_members(
    data: DebugSetGameMembersRequest,
    db: Session = Depends(get_db_dep),
):
    game = db.get(Game, data.game_id)
    if not game:
        return {"detail": "Game not found"}

    for upd in data.updates:
        gm = db.get(GameMember, upd.member_id)
        if not gm or gm.game_id != data.game_id:
            return {"detail": "GameMember not found"}

        if upd.role_type is not None:
            gm.role_type = upd.role_type
            if upd.team is None:
                gm.team = "WOLF" if upd.role_type in ("WEREWOLF", "MADMAN") else "VILLAGE"
        if upd.team is not None:
            gm.team = upd.team
        if upd.alive is not None:
            gm.alive = upd.alive
        db.add(gm)

    if data.reset_votes:
        db.query(DayVote).filter(DayVote.game_id == data.game_id).delete()
        db.query(WolfVote).filter(WolfVote.game_id == data.game_id).delete()
        db.query(SeerInspect).filter(SeerInspect.game_id == data.game_id).delete()
        db.query(KnightGuard).filter(KnightGuard.game_id == data.game_id).delete()
        if hasattr(game, "vote_round"):
            game.vote_round = 0
        if hasattr(game, "tie_streak"):
            game.tie_streak = 0
        db.add(game)

    db.commit()

    members = (
        db.query(GameMember)
        .filter(GameMember.game_id == data.game_id)
        .order_by(GameMember.order_no.asc())
        .all()
    )
    return {
        "game_id": game.id,
        "updated": [
            {
                "id": m.id,
                "role_type": m.role_type,
                "team": m.team,
                "alive": m.alive,
            }
            for m in members
        ],
    }
