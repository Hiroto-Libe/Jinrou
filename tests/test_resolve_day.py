# tests/test_resolve_day.py

import uuid
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.game import Game, GameMember, DayVote
from app.models.room import Room, RoomMember
from app.schemas.day import DayResolveRequest
from app.api.v1.games import resolve_day_simple


def _create_game_for_day_resolve(
    db: Session,
    wolf_count: int = 1,
    village_count: int = 4,
) -> tuple[Game, list[GameMember]]:
    """
    昼決着テスト用のゲームとメンバーを作るユーティリティ。
    デフォルトは 狼1 / 村4 → 村を1人処刑してもゲーム継続（NIGHTに進む）想定。
    """
    room = Room(
        id="dummy-room",
        name="day resolve room",
    )
    db.add(room)
    db.flush()

    game = Game(
        id=str(uuid.uuid4()),
        room_id=room.id,
        status="DAY_DISCUSSION",
        curr_day=1,
        curr_night=1,
    )
    db.add(game)
    db.commit()
    db.refresh(game)

    members: list[GameMember] = []

    # 狼メンバー
    for i in range(wolf_count):
        room_member_id = f"wolf-room-member-{i}"
        rm = RoomMember(
            id=room_member_id,
            room_id=room.id,
            display_name=f"Wolf{i+1}",
            avatar_url=None,
            is_host=(i == 0),
        )
        db.add(rm)

        m = GameMember(
            id=str(uuid.uuid4()),
            game_id=game.id,
            room_member_id=room_member_id,
            display_name=f"Wolf{i+1}",
            avatar_url=None,
            role_type="WEREWOLF",
            team="WOLF",
            alive=True,
            order_no=len(members) + 1,
        )
        db.add(m)
        members.append(m)

    # 村メンバー
    for i in range(village_count):
        room_member_id = f"vill-room-member-{i}"
        rm = RoomMember(
            id=room_member_id,
            room_id=room.id,
            display_name=f"Villager{i+1}",
            avatar_url=None,
            is_host=False,
        )
        db.add(rm)

        m = GameMember(
            id=str(uuid.uuid4()),
            game_id=game.id,
            room_member_id=room_member_id,
            display_name=f"Villager{i+1}",
            avatar_url=None,
            role_type="VILLAGER",
            team="VILLAGE",
            alive=True,
            order_no=len(members) + 1,
        )
        db.add(m)
        members.append(m)

    db.commit()
    for m in members:
        db.refresh(m)

    return game, members


def test_resolve_day_simple_executes_top_voted_and_sets_last_executed(db: Session):
    """
    最多得票のプレイヤーが追放され、
    - victim.alive == False
    - game.last_executed_member_id に victim.id が入る
    - game.status が NIGHT に進む（この構成ではゲーム継続）
    ことを確認する。
    """
    game, members = _create_game_for_day_resolve(db, wolf_count=1, village_count=4)

    # 狼1 / 村4 のうち、村人の1人を処刑ターゲットにする
    # members[0] が狼、members[1:] が全員村 という前提
    victim = members[2]  # 適当な村人

    # 全員が victim に投票したことにする
    for voter in members:
        vote = DayVote(
            id=str(uuid.uuid4()),
            game_id=game.id,
            day_no=game.curr_day,
            voter_member_id=voter.id,
            target_member_id=victim.id,
        )
        db.add(vote)
    db.commit()

    # 実行
    host_game_member = next(
        m for m in members if m.room_member_id == "wolf-room-member-0"
    )
    result = resolve_day_simple(
        game_id=game.id,
        data=DayResolveRequest(requester_member_id=host_game_member.id),
        db=db,
    )

    db.refresh(game)
    db.refresh(victim)

    assert result["game_id"] == game.id
    assert result["day_no"] == 1
    assert result["victim"]["id"] == victim.id
    assert result["victim"]["alive"] is False

    # Game 側にも反映されていること
    assert game.last_executed_member_id == victim.id

    # この人数配分（狼1 / 村4 で村1人処刑）ではゲーム継続 → NIGHT
    assert result["status"] == "NIGHT"
    assert game.status == "NIGHT"


def test_resolve_day_simple_tie_votes_executes_one_of_them(db: Session):
    """
    票数同数の候補が複数いる場合、
    その中からランダムで1人だけが追放されることを確認する。
    """
    game, members = _create_game_for_day_resolve(db, wolf_count=1, village_count=4)

    # 候補となる村人2人
    candidate1 = members[2]
    candidate2 = members[3]

    voters = members  # 全員投票する前提

    # 先頭2人が candidate1 に、残り2人が candidate2 に投票（2票 vs 2票）
    for i, voter in enumerate(voters[:4]):  # 4人だけ使う
        target = candidate1 if i < 2 else candidate2
        vote = DayVote(
            id=str(uuid.uuid4()),
            game_id=game.id,
            day_no=game.curr_day,
            voter_member_id=voter.id,
            target_member_id=target.id,
        )
        db.add(vote)
    db.commit()

    # 実行
    host_game_member = next(
        m for m in members if m.room_member_id == "wolf-room-member-0"
    )
    result = resolve_day_simple(
        game_id=game.id,
        data=DayResolveRequest(requester_member_id=host_game_member.id),
        db=db,
    )

    db.refresh(game)
    db.refresh(candidate1)
    db.refresh(candidate2)

    victim_id = result["victim"]["id"]

    # どちらか一方だけが死亡していること
    assert victim_id in (candidate1.id, candidate2.id)
    dead_count = sum(
        1 for m in (candidate1, candidate2) if m.alive is False
    )
    assert dead_count == 1

    # last_executed_member_id もどちらかになっている
    assert game.last_executed_member_id in (candidate1.id, candidate2.id)

    # この構成では依然としてゲーム継続 → NIGHT
    assert result["status"] == "NIGHT"
    assert game.status == "NIGHT"


def test_resolve_day_simple_raises_when_not_day_discussion(db: Session):
    """
    Game.status が DAY_DISCUSSION 以外の場合は 400 エラーになること。
    """
    game, members = _create_game_for_day_resolve(db, wolf_count=1, village_count=4)
    game.status = "NIGHT"  # 昼議論状態ではない
    db.add(game)
    db.commit()
    db.refresh(game)

    host_game_member = next(
        m for m in members if m.room_member_id == "wolf-room-member-0"
    )

    with pytest.raises(HTTPException) as exc:
        resolve_day_simple(
            game_id=game.id,
            data=DayResolveRequest(requester_member_id=host_game_member.id),
            db=db,
        )

    assert exc.value.status_code == 400
    assert "DAY_DISCUSSION" in exc.value.detail


def test_resolve_day_simple_raises_when_no_votes(db: Session):
    """
    昼の投票が1件もない場合は 400 エラー (No day votes to resolve) になること。
    """
    game, members = _create_game_for_day_resolve(db, wolf_count=1, village_count=4)
    host_game_member = next(
        m for m in members if m.room_member_id == "wolf-room-member-0"
    )

    with pytest.raises(HTTPException) as exc:
        resolve_day_simple(
            game_id=game.id,
            data=DayResolveRequest(requester_member_id=host_game_member.id),
            db=db,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "No day votes to resolve"
