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


def test_resolve_day_simple_tie_votes_enters_runoff_first(db: Session):
    """
    通常投票で同率1位が複数いる場合、まず決選投票(RUNOFF)へ移行することを確認する。
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
    result1 = resolve_day_simple(
        game_id=game.id,
        data=DayResolveRequest(requester_member_id=host_game_member.id),
        db=db,
    )

    db.refresh(game)
    db.refresh(candidate1)
    db.refresh(candidate2)

    assert result1["status"] == "RUNOFF"
    assert set(result1["candidate_ids"]) == {candidate1.id, candidate2.id}
    assert candidate1.alive is True
    assert candidate2.alive is True
    assert game.status == "DAY_DISCUSSION"
    assert game.last_executed_member_id is None

    # 決選投票を作成（candidate1 を最多票にする）
    for voter in members[:3]:
        vote = DayVote(
            id=str(uuid.uuid4()),
            game_id=game.id,
            day_no=game.curr_day,
            voter_member_id=voter.id,
            target_member_id=candidate1.id if voter != members[0] else candidate2.id,
        )
        db.add(vote)
    db.commit()

    result2 = resolve_day_simple(
        game_id=game.id,
        data=DayResolveRequest(requester_member_id=host_game_member.id),
        db=db,
    )

    db.refresh(game)
    db.refresh(candidate1)
    db.refresh(candidate2)
    assert result2["status"] == "NIGHT"
    assert result2["victim"]["id"] == candidate1.id
    assert candidate1.alive is False
    assert game.last_executed_member_id == candidate1.id


def test_resolve_day_simple_runoff_supports_three_way_tie(db: Session):
    """
    同率1位が3人以上でも RUNOFF の候補に全員含まれることを確認する。
    """
    game, members = _create_game_for_day_resolve(db, wolf_count=1, village_count=6)

    c1 = members[2]
    c2 = members[3]
    c3 = members[4]
    voters = members[:6]
    targets = [c1, c1, c2, c2, c3, c3]  # 2-2-2 の同率トップ3名

    for voter, target in zip(voters, targets):
        vote = DayVote(
            id=str(uuid.uuid4()),
            game_id=game.id,
            day_no=game.curr_day,
            voter_member_id=voter.id,
            target_member_id=target.id,
        )
        db.add(vote)
    db.commit()

    host_game_member = next(
        m for m in members if m.room_member_id == "wolf-room-member-0"
    )
    result = resolve_day_simple(
        game_id=game.id,
        data=DayResolveRequest(requester_member_id=host_game_member.id),
        db=db,
    )

    assert result["status"] == "RUNOFF"
    assert set(result["candidate_ids"]) == {c1.id, c2.id, c3.id}


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
