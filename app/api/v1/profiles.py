# app/api/v1/profiles.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from ...api.deps import get_db_dep
from ...models.profile import Profile
from ...schemas.profile import ProfileCreate, ProfileOut

router = APIRouter(prefix="/profiles", tags=["profiles"])

@router.get("/{profile_id}", response_model=ProfileOut)
def get_profile(
    profile_id: str,
    db: Session = Depends(get_db_dep),
):
    profile = db.get(Profile, profile_id)
    # 物理削除でも論理削除でも OK
    # - 物理削除: db.get(...) が None → 404
    # - 論理削除: is_deleted = True → 404
    if not profile or getattr(profile, "is_deleted", False):
        raise HTTPException(status_code=404, detail="Profile not found")

    return profile


@router.post("", response_model=ProfileOut)
def create_profile(
    data: ProfileCreate,
    db: Session = Depends(get_db_dep),
):
    """プロフィール新規登録"""
    profile = Profile(
        id=str(uuid.uuid4()),
        display_name=data.display_name,
        avatar_url=data.avatar_url,
        note=data.note,
        is_deleted=False,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("", response_model=list[ProfileOut])
def list_profiles(
    active_only: bool = True,
    db: Session = Depends(get_db_dep),
):
    """プロフィール一覧取得（active_only=True なら is_deleted=False だけ）"""
    q = db.query(Profile)
    if active_only:
        q = q.filter(Profile.is_deleted == False)  # noqa: E712
    return q.all()


@router.delete("/{profile_id}", status_code=204)
def delete_profile(
    profile_id: str,
    db: Session = Depends(get_db_dep),
):
    """ソフトデリート（is_deleted=True）"""
    profile = db.get(Profile, profile_id)
    if not profile or profile.is_deleted:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile.is_deleted = True
    db.add(profile)
    db.commit()
    return
