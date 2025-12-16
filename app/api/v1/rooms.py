# app/api/v1/rooms.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from ...api.deps import get_db_dep
from ...models.room import Room, RoomRoster, RoomMember
from ...models.profile import Profile
from app.schemas.room import RoomOut 
from ...schemas.room import (
    RoomCreate,
    RoomOut,
    RoomRosterCreate,
    RoomRosterItem,
    RoomMemberListItem,
    BulkMembersFromRosterRequest,
    RoomRosterJoinRequest,  
)
from app.schemas.room import RoomRosterItem, RoomRosterJoinRequest

router = APIRouter(
    prefix="/rooms",   # ★ ここを /rooms に固定
    tags=["rooms"],
)


# -----------------------------
# 部屋の作成・一覧
# -----------------------------

@router.post("", response_model=RoomOut)
def create_room(
    data: RoomCreate,
    db: Session = Depends(get_db_dep),
):
    room = Room(
        id=str(uuid.uuid4()),
        name=data.name,
        owner_profile_id=data.owner_profile_id,
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@router.get("", response_model=list[RoomOut])
def list_rooms(
    db: Session = Depends(get_db_dep),
):
    return db.query(Room).all()


# -----------------------------
# 出席簿（room_roster）
# -----------------------------

@router.post("/{room_id}/roster", response_model=RoomRosterItem)
def add_to_roster(
    room_id: str,
    data: RoomRosterJoinRequest,  # ★ 正しいシグネチャ
    db: Session = Depends(get_db_dep),
):
    # 1. room の存在チェック
    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # 2. display_name から Profile を新規作成（簡易実装）
    profile = Profile(
        id=str(uuid.uuid4()),
        display_name=data.display_name,
        avatar_url=None,
        is_deleted=False,
    )
    db.add(profile)
    db.flush()  # profile.id を取得するため

    # 3. RoomRoster を作成
    roster = RoomRoster(
        id=str(uuid.uuid4()),
        room_id=room_id,
        profile_id=profile.id,
        alias_name=None,
    )
    db.add(roster)
    db.commit()
    db.refresh(roster)

    # 4. レスポンス用に整形
    display_name = roster.alias_name or profile.display_name
    return RoomRosterItem(
        id=roster.id,
        profile_id=profile.id,
        display_name=display_name,
        alias_name=roster.alias_name,
        avatar_url=profile.avatar_url,
    )



@router.get("/{room_id}/roster", response_model=list[RoomRosterItem])
def list_roster(
    room_id: str,
    db: Session = Depends(get_db_dep),
):
    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    q = (
        db.query(RoomRoster, Profile)
        .join(Profile, RoomRoster.profile_id == Profile.id)
        .filter(
            RoomRoster.room_id == room_id,
            Profile.is_deleted == False,  # noqa: E712
        )
    )

    items: list[RoomRosterItem] = []
    for rr, prof in q.all():
        items.append(
            RoomRosterItem(
                id=rr.id,
                profile_id=prof.id,
                display_name=rr.alias_name or prof.display_name,
                alias_name=rr.alias_name,
                avatar_url=prof.avatar_url,
            )
        )
    return items


# -----------------------------
# 当日参加者（room_members）
# -----------------------------

@router.post(
    "/{room_id}/members/bulk_from_roster",
    response_model=list[RoomMemberListItem],
)
def create_members_from_roster(
    room_id: str,
    body: BulkMembersFromRosterRequest | None = None,
    db: Session = Depends(get_db_dep),
):
    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # ベースのクエリ：その部屋の有効な roster 全員
    base_q = (
        db.query(RoomRoster, Profile)
        .join(Profile, RoomRoster.profile_id == Profile.id)
        .filter(
            RoomRoster.room_id == room_id,
            Profile.is_deleted == False,  # noqa: E712
        )
    )

    # body があり、profile_ids が指定されている場合だけ絞り込む
    if body is not None and body.profile_ids:
        q = base_q.filter(RoomRoster.profile_id.in_(body.profile_ids))
    else:
        # body なし or profile_ids 空 → roster 全員を対象
        q = base_q

    rows = q.all()
    if not rows:
        return []

    members: list[RoomMember] = []
    for rr, prof in rows:
        display_name = rr.alias_name or prof.display_name
        m = RoomMember(
            id=str(uuid.uuid4()),
            room_id=room_id,
            display_name=display_name,
            avatar_url=prof.avatar_url,
        )
        db.add(m)
        members.append(m)

    db.commit()
    for m in members:
        db.refresh(m)

    return [RoomMemberListItem.model_validate(m) for m in members]

@router.get("/{room_id}/members", response_model=list[RoomMemberListItem])
def list_room_members(
    room_id: str,
    db: Session = Depends(get_db_dep),
):
    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    members = (
        db.query(RoomMember)
        .filter(RoomMember.room_id == room_id)
        .order_by(RoomMember.joined_at)
        .all()
    )
    return [RoomMemberListItem.model_validate(m) for m in members]

@router.get("/{room_id}", response_model=RoomOut)
def get_room(room_id: str, db: Session = Depends(get_db_dep)):
    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="room not found")
    return room