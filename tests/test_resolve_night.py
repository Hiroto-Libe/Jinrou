# tests/test_resolve_night.py

from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.game import Game, GameMember, WolfVote
from app.models.knight import KnightGuard

from app.api.v1.games import resolve_night_simple


def _create_game_for_night(db: Session, *, wolves: int, villagers: int) -> tuple[Game, list[GameMember], list[GameMember]]:
    """NIGHT 状態のゲームとメンバーをまとめて作る小さなヘルパー。"""
    game = Game(
        id=str(uuid4()),
        room_id="room-1",
        status="NIGHT",
        curr_night=1,
        curr_day=1,
    )
    db.add(game)
    db.commit()
    db.refresh(game)

    members: list[GameMember] = []
    order_no = 1

    # 狼メンバー
    for i in range(wolves):
        gm = GameMember(
            id=str(uuid4()),
            game_id=game.id,
            room_member_id=f"rm-wolf-{i}",
            display_name=f"Wolf-{i}",
            avatar_url=None,
            role_type="WEREWOLF",
            team="WOLF",
            alive=True,
            order_no=order_no,
        )
        order_no += 1
        db.add(gm)
        members.append(gm)

    # 村人メンバー
    for i in range(villagers):
        gm = GameMember(
            id=str(uuid4()),
            game_id=game.id,
            room_member_id=f"rm-vill-{i}",
            display_name=f"Villager-{i}",
            avatar_url=None,
            role_type="VILLAGER",
            team="VILLAGE",
            alive=True,
            order_no=order_no,
        )
        order_no += 1
        db.add(gm)
        members.append(gm)

    db.commit()

    wolves_members = [m for m in members if m.team == "WOLF"]
    village_members = [m for m in members if m.team == "VILLAGE"]

    return game, wolves_members, village_members


def test_resolve_night_simple_kills_target_when_not_guarded(db: Session):
    """
    騎士の護衛が無い場合:
    - 最多ポイントを集めたターゲットが死亡する
    - ゲームステータスは DAY_DISCUSSION に進む
    - この人数構成ではまだゲームは継続（ONGOING）
    """
    # 狼1 / 村3 のゲーム
    game, wolves, villages = _create_game_for_night(db, wolves=1, villagers=3)

    attacker = wolves[0]
    victim = villages[0]

    vote = WolfVote(
        id=str(uuid4()),
        game_id=game.id,
        night_no=game.curr_night,
        wolf_member_id=attacker.id,
        target_member_id=victim.id,
        priority_level=1,
        points_at_vote=game.wolf_vote_lvl1_point,
    )
    db.add(vote)
    db.commit()

    result = resolve_night_simple(game_id=game.id, db=db)

    db.refresh(game)
    db.refresh(victim)

    assert result["guarded_success"] is False
    assert result["victim"]["id"] == victim.id
    assert victim.alive is False
    # この人数だとまだ勝敗はつかず、ステータスは DAY_DISCUSSION のまま
    assert result["status"] == "DAY_DISCUSSION"
    assert game.status == "DAY_DISCUSSION"


def test_resolve_night_simple_no_kill_when_guarded(db: Session):
    """
    騎士に護衛されている場合:
    - 襲撃対象は死亡しない
    - victim は None で返される
    - guarded_success が True になる
    """
    game, wolves, villages = _create_game_for_night(db, wolves=1, villagers=3)

    attacker = wolves[0]
    victim = villages[0]

    # 狼の投票
    vote = WolfVote(
        id=str(uuid4()),
        game_id=game.id,
        night_no=game.curr_night,
        wolf_member_id=attacker.id,
        target_member_id=victim.id,
        priority_level=1,
        points_at_vote=game.wolf_vote_lvl1_point,
    )
    db.add(vote)

    # 騎士の護衛（対象だけ合っていれば OK）
    guard = KnightGuard(
        id=str(uuid4()),
        game_id=game.id,
        night_no=game.curr_night,
        knight_member_id=str(uuid4()),  # テストなのでダミーIDで十分
        target_member_id=victim.id,
    )
    db.add(guard)
    db.commit()

    result = resolve_night_simple(game_id=game.id, db=db)

    db.refresh(game)
    db.refresh(victim)

    assert result["guarded_success"] is True
    assert result["victim"] is None
    assert victim.alive is True
    assert result["status"] == "DAY_DISCUSSION"
    assert game.status == "DAY_DISCUSSION"


def test_resolve_night_simple_game_ends_with_wolf_win(db: Session):
    """
    襲撃の結果、狼数 >= 村人数 になった場合:
    - resolve_night_simple 内の勝敗判定で WOLF_WIN になる
    """
    # 狼2 / 村2 → 村人1人が襲われると 狼2 / 村1 で狼勝利
    game, wolves, villages = _create_game_for_night(db, wolves=2, villagers=2)

    attacker = wolves[0]
    victim = villages[0]

    vote = WolfVote(
        id=str(uuid4()),
        game_id=game.id,
        night_no=game.curr_night,
        wolf_member_id=attacker.id,
        target_member_id=victim.id,
        priority_level=1,
        points_at_vote=game.wolf_vote_lvl1_point,
    )
    db.add(vote)
    db.commit()

    result = resolve_night_simple(game_id=game.id, db=db)

    db.refresh(game)
    db.refresh(victim)

    assert victim.alive is False
    assert result["victim"]["id"] == victim.id
    # 勝敗判定の結果、狼陣営の勝利になっているはず
    assert result["status"] == "WOLF_WIN"
    assert game.status == "WOLF_WIN"
