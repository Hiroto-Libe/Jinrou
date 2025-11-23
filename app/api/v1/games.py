# app/api/v1/games.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
import uuid
import random 
from typing import List, Optional

from ...api.deps import get_db_dep
from ...models.room import RoomMember
from ...models.game import Game, GameMember, WolfVote, DayVote 
from ...schemas.seer import SeerFirstWhiteOut  # ★ 追加
from ...schemas.game import GameCreate, GameOut, GameMemberOut
from ...schemas.night import (
    WolfVoteCreate,
    WolfVoteOut,
    WolfTallyItem,
    WolfTallyOut,
)
from ...schemas.day import (  # ★ 追加
    DayVoteCreate,
    DayVoteOut,
    DayTallyItem,
    DayTallyOut,
)

router = APIRouter(prefix="/games", tags=["games"])


# -----------------------------
# 🎮 ゲーム作成
# -----------------------------
@router.post("", response_model=GameOut)
def create_game(
    data: GameCreate,
    db: Session = Depends(get_db_dep),
):
    # 当日メンバーがいないとゲーム開始できない
    members = (
        db.query(RoomMember)
        .filter(RoomMember.room_id == data.room_id)
        .all()
    )
    if not members:
        raise HTTPException(status_code=400, detail="No room members to start game")

    g = Game(
        id=str(uuid.uuid4()),
        room_id=data.room_id,
    )

    # 設定が届いていれば反映
    if data.settings:
        s = data.settings
        g.show_votes_public = s.show_votes_public
        g.day_timer_sec = s.day_timer_sec
        g.knight_self_guard = s.knight_self_guard
        g.knight_consecutive_guard = s.knight_consecutive_guard
        g.allow_no_kill = s.allow_no_kill
        g.wolf_vote_lvl1_point = s.wolf_vote_lvl1_point
        g.wolf_vote_lvl2_point = s.wolf_vote_lvl2_point
        g.wolf_vote_lvl3_point = s.wolf_vote_lvl3_point

    db.add(g)
    db.commit()
    db.refresh(g)
    return g


# -----------------------------
# 🧩 役職配布
# -----------------------------
@router.post("/{game_id}/role_assign", response_model=list[GameMemberOut])
def assign_roles(
    game_id: str,
    db: Session = Depends(get_db_dep),
):
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if game.status not in ("WAITING", "ROLE_ASSIGN"):
        raise HTTPException(status_code=400, detail="Game already started")

    # 参加メンバー（room_members）を取得
    room_members: List[RoomMember] = (
        db.query(RoomMember)
        .filter(RoomMember.room_id == game.room_id)
        .all()
    )
    n = len(room_members)
    if n < 6:
        raise HTTPException(status_code=400, detail="Need at least 6 players")

    # 人数に応じた役職構成
    roles = decide_roles(n)
    if len(roles) != n:
        raise HTTPException(status_code=500, detail="Role assignment mismatch")

    import random
    shuffled = room_members[:]
    random.shuffle(shuffled)

    game_members: list[GameMember] = []
    for order_no, (rm, (role_type, team)) in enumerate(zip(shuffled, roles), start=1):
        gm = GameMember(
            id=str(uuid.uuid4()),
            game_id=game.id,
            room_member_id=rm.id,
            display_name=rm.display_name,
            avatar_url=rm.avatar_url,
            role_type=role_type,
            team=team,
            alive=True,
            order_no=order_no,
        )
        db.add(gm)
        game_members.append(gm)

    game.status = "ROLE_ASSIGN"
    db.commit()

    for gm in game_members:
        db.refresh(gm)

    return [GameMemberOut.model_validate(gm) for gm in game_members]

# -----------------------------
# 🔍 ゲームの状態を強制変更するAPI
# -----------------------------
@router.post("/{game_id}/debug_set_status")
def debug_set_status(
    game_id: str,
    status: str,
    db: Session = Depends(get_db_dep),
):
    """
    ★テスト用★ ゲームのステータスを強制的に変更する。
    本番運用では削除 or 認証付きにする想定。
    """
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    game.status = status
    db.add(game)
    db.commit()
    db.refresh(game)
    return {"game_id": game.id, "status": game.status}


# -----------------------------
# 🔍 ゲーム情報取得
# -----------------------------
@router.get("/{game_id}", response_model=GameOut)
def get_game(
    game_id: str,
    db: Session = Depends(get_db_dep),
):
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game


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


@router.post("/{game_id}/day_vote", response_model=DayVoteOut)
def day_vote(
    game_id: str,
    data: DayVoteCreate,
    db: Session = Depends(get_db_dep),
):
    """
    昼の投票（シンプル版）:
    - ゲームが DAY_DISCUSSION 状態のときのみ有効
    - 生存しているプレイヤーだけ投票可能
    - ターゲットも生存しているプレイヤーのみ
    - 同じ voter が再投票した場合は上書き
    """
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if game.status != "DAY_DISCUSSION":
        raise HTTPException(status_code=400, detail="Game is not in DAY_DISCUSSION phase")

    voter = db.get(GameMember, data.voter_member_id)
    if not voter or voter.game_id != game_id:
        raise HTTPException(status_code=404, detail="Voter member not found")
    if not voter.alive:
        raise HTTPException(status_code=400, detail="Dead player cannot vote")

    target = db.get(GameMember, data.target_member_id)
    if not target or target.game_id != game_id:
        raise HTTPException(status_code=404, detail="Target member not found")
    if not target.alive:
        raise HTTPException(status_code=400, detail="Target is already dead")

    if voter.id == target.id:
        raise HTTPException(status_code=400, detail="Player cannot vote for themselves")

    day_no = game.curr_day

    # 既存投票があれば上書き
    existing: DayVote | None = (
        db.query(DayVote)
        .filter(
            DayVote.game_id == game_id,
            DayVote.day_no == day_no,
            DayVote.voter_member_id == voter.id,
        )
        .one_or_none()
    )

    if existing:
        existing.target_member_id = target.id
        vote = existing
    else:
        vote = DayVote(
            id=str(uuid.uuid4()),
            game_id=game_id,
            day_no=day_no,
            voter_member_id=voter.id,
            target_member_id=target.id,
        )
        db.add(vote)

    db.commit()
    db.refresh(vote)
    return DayVoteOut.model_validate(vote)


def _judge_game_result(game_id: str, db: Session) -> dict:
    """
    生存メンバーから勝敗を判定するヘルパー関数。
    戻り値は dict で result / wolf_alive / village_alive / reason を含む。
    """
    alive_members = (
        db.query(GameMember)
        .filter(GameMember.game_id == game_id, GameMember.alive == True)
        .all()
    )

    wolves = [m for m in alive_members if m.team == "WOLF"]
    villages = [m for m in alive_members if m.team == "VILLAGE"]

    wolf_count = len(wolves)
    village_count = len(villages)

    if wolf_count == 0:
        return {
            "result": "VILLAGE_WIN",
            "wolf_alive": wolf_count,
            "village_alive": village_count,
            "reason": "All werewolves are dead.",
        }
    elif wolf_count >= village_count:
        return {
            "result": "WOLF_WIN",
            "wolf_alive": wolf_count,
            "village_alive": village_count,
            "reason": "Wolves are equal to or more than villages.",
        }
    else:
        return {
            "result": "ONGOING",
            "wolf_alive": wolf_count,
            "village_alive": village_count,
            "reason": "Game continues.",
        }

# -----------------------------
# 🧮 夜の人狼投票 集計
# -----------------------------
@router.get("/{game_id}/wolves/tally", response_model=WolfTallyOut)
def wolf_tally(
    game_id: str,
    night_no: Optional[int] = None,
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


@router.post("/{game_id}/resolve_night_simple")
def resolve_night_simple(
    game_id: str,
    db: Session = Depends(get_db_dep),
):
    """
    シンプル版の夜明け処理:
    - 現在の night_no の狼投票を集計
    - 合計ポイント最大のターゲットを1人選び、alive=False にする
    - Game.status を DAY_DISCUSSION に変更
    """
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if game.status != "NIGHT":
        raise HTTPException(status_code=400, detail="Game is not in NIGHT phase")

    night_no = game.curr_night

    # target ごとのポイント合計＋票数を集計
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

    if not rows:
        raise HTTPException(status_code=400, detail="No wolf votes to resolve")

    # 最大ポイントを求める
    max_points = max(int(r.total_points) for r in rows)

    # 最大ポイントの候補をすべて集める（同点対応）
    candidates = [
        r for r in rows
        if int(r.total_points) == max_points
    ]

    # 同点ならランダムで1人選ぶ
    chosen = random.choice(candidates)

    victim = db.get(GameMember, chosen.target_member_id)
    if not victim:
        raise HTTPException(status_code=500, detail="Victim GameMember not found")

    # 襲撃で死亡扱い
    victim.alive = False

    # ゲームステータスを朝に進める（シンプル版）
    game.status = "DAY_DISCUSSION"

    db.add(victim)
    db.add(game)
    db.commit()
    db.refresh(victim)
    db.refresh(game)

    judge = _judge_game_result(game.id, db)
    if judge["result"] != "ONGOING":
        game.status = judge["result"]
        db.commit()
        db.refresh(game)

    return {
        "game_id": game.id,
        "night_no": night_no,
        "status": game.status,
        "victim": {
            "id": victim.id,
            "display_name": victim.display_name,
            "role_type": victim.role_type,
            "team": victim.team,
            "alive": victim.alive,
        },
        "tally": {
            "target_member_id": victim.id,
            "total_points": max_points,
            "vote_count": int(chosen.vote_count),
        },
    }


@router.get("/{game_id}/members", response_model=list[GameMemberOut])
def list_game_members(
    game_id: str,
    db: Session = Depends(get_db_dep),
):
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    members = (
        db.query(GameMember)
        .filter(GameMember.game_id == game_id)
        .order_by(GameMember.order_no)
        .all()
    )
    return [GameMemberOut.model_validate(m) for m in members]


# -----------------------------
# 👥 人数に応じた役職構成
# -----------------------------
def decide_roles(n: int) -> list[tuple[str, str]]:
    """
    n人に対する役職構成を返す。
    戻り値: [(role_type, team), ...] * n
    """
    if n == 6:
        base = ["WEREWOLF", "WEREWOLF", "SEER", "KNIGHT", "VILLAGER", "VILLAGER"]
    elif n == 7:
        base = ["WEREWOLF", "WEREWOLF", "SEER", "KNIGHT", "VILLAGER", "VILLAGER", "VILLAGER"]
    elif n == 8:
        base = ["WEREWOLF", "WEREWOLF", "SEER", "MEDIUM", "KNIGHT", "VILLAGER", "VILLAGER", "VILLAGER"]
    elif n == 9:
        base = ["WEREWOLF", "WEREWOLF", "SEER", "MEDIUM", "KNIGHT"] + ["VILLAGER"] * 4
    elif n == 10:
        base = ["WEREWOLF", "WEREWOLF", "SEER", "MEDIUM", "KNIGHT"] + ["VILLAGER"] * 5
    else:
        # 雑なデフォルト：狼 = n//4人、他は SEER/MEDIUM/KNIGHT + 村人
        wolves = max(2, n // 4)
        base = ["WEREWOLF"] * wolves + ["SEER", "MEDIUM", "KNIGHT"]
        while len(base) < n:
            base.append("VILLAGER")

    def to_team(role: str) -> str:
        return "WOLF" if role == "WEREWOLF" else "VILLAGE"

    return [(r, to_team(r)) for r in base]

@router.get("/{game_id}/day_tally", response_model=DayTallyOut)
def day_tally(
    game_id: str,
    day_no: Optional[int] = None,
    db: Session = Depends(get_db_dep),
):
    """
    昼投票の集計:
    - target_member ごとの票数をカウント
    - day_no を指定しなければ game.curr_day を使用
    """
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if day_no is None:
        day_no = game.curr_day

    rows = (
        db.query(
            DayVote.target_member_id,
            func.count().label("vote_count"),
        )
        .filter(
            DayVote.game_id == game_id,
            DayVote.day_no == day_no,
        )
        .group_by(DayVote.target_member_id)
        .all()
    )

    items = [
        DayTallyItem(
            target_member_id=target_member_id,
            vote_count=int(vote_count),
        )
        for target_member_id, vote_count in rows
    ]

    return DayTallyOut(
        game_id=game_id,
        day_no=day_no,
        items=items,
    )


@router.post("/{game_id}/resolve_day_simple")
def resolve_day_simple(
    game_id: str,
    db: Session = Depends(get_db_dep),
):
    """
    シンプル版の昼決着:
    - 現在の day_no の投票を集計
    - 最多得票者を一人追放（alive=False）
    - 同票ならランダムに選ぶ
    - Game.status を NIGHT に変更し、curr_day/curr_night を進める
    ※ 勝敗判定はここではまだしない（後で拡張）
    """
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if game.status != "DAY_DISCUSSION":
        raise HTTPException(status_code=400, detail="Game is not in DAY_DISCUSSION phase")

    day_no = game.curr_day

    rows = (
        db.query(
            DayVote.target_member_id,
            func.count().label("vote_count"),
        )
        .filter(
            DayVote.game_id == game_id,
            DayVote.day_no == day_no,
        )
        .group_by(DayVote.target_member_id)
        .all()
    )

    if not rows:
        raise HTTPException(status_code=400, detail="No day votes to resolve")

    max_votes = max(int(r.vote_count) for r in rows)
    candidates = [r for r in rows if int(r.vote_count) == max_votes]

    chosen = random.choice(candidates)

    victim = db.get(GameMember, chosen.target_member_id)
    if not victim:
        raise HTTPException(status_code=500, detail="Victim GameMember not found")

    victim.alive = False

    # 次の夜へ進める（シンプル版）
    game.status = "NIGHT"
    game.curr_day = game.curr_day + 1
    game.curr_night = game.curr_night + 1

    db.add(victim)
    db.add(game)
    db.commit()
    db.refresh(victim)
    db.refresh(game)

    # --- ★ 勝敗判定（昼の処刑後） ---
    judge = _judge_game_result(game.id, db)
    if judge["result"] != "ONGOING":
        game.status = judge["result"]      # "VILLAGE_WIN" or "WOLF_WIN"
        db.commit()
        db.refresh(game)

    return {
        "game_id": game.id,
        "day_no": day_no,
        "status": game.status,
        "victim": {
            "id": victim.id,
            "display_name": victim.display_name,
            "role_type": victim.role_type,
            "team": victim.team,
            "alive": victim.alive,
        },
        "tally": {
            "target_member_id": victim.id,
            "vote_count": max_votes,
        },
    }


@router.get("/{game_id}/seer/first_white", response_model=SeerFirstWhiteOut)
def get_or_create_seer_first_white(
    game_id: str,
    db: Session = Depends(get_db_dep),
):
    """
    初日白通知API:
    - まだ白通知ターゲットが決まっていなければ、村陣営からランダムに1人選び、
      game.seer_first_white_target_id に保存する。
    - すでに決まっていれば、その情報を返す（idempotent）。
    - 前提: このゲームに占い師(SEER)が1人存在する。
    """

    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # 1. 占い師（SEER）を特定
    seer = (
        db.query(GameMember)
        .filter(
            GameMember.game_id == game_id,
            GameMember.role_type == "SEER",
        )
        .one_or_none()
    )
    if not seer:
        raise HTTPException(status_code=400, detail="No seer in this game")

    # 2. すでに白通知ターゲットが決まっている場合 → それを返す
    if game.seer_first_white_target_id:
        target = db.get(GameMember, game.seer_first_white_target_id)
        if not target:
            # データ不整合（念のため）
            raise HTTPException(status_code=500, detail="Seer first white target not found")
        return SeerFirstWhiteOut(
            game_id=game.id,
            seer_member_id=seer.id,
            target_member_id=target.id,
            target_display_name=target.display_name,
            is_wolf=False,  # このAPIは「人狼ではない」ことを知らせる
        )

    # 3. まだ決まっていない場合 → 村陣営からランダムに1人選ぶ
    candidates = (
        db.query(GameMember)
        .filter(
            GameMember.game_id == game_id,
            GameMember.team == "VILLAGE",   # 村陣営
            GameMember.id != seer.id,       # 占い師本人は除外
        )
        .all()
    )

    if not candidates:
        raise HTTPException(status_code=400, detail="No village candidate for seer white")

    target = random.choice(candidates)

    # 4. game に保存して永続化
    game.seer_first_white_target_id = target.id
    db.add(game)
    db.commit()
    db.refresh(game)

    # 5. レスポンス
    return SeerFirstWhiteOut(
        game_id=game.id,
        seer_member_id=seer.id,
        target_member_id=target.id,
        target_display_name=target.display_name,
        is_wolf=False,
    )


@router.get("/{game_id}/judge")
def judge_game(
    game_id: str,
    db: Session = Depends(get_db_dep),
):
    """
    現時点の生存状況から勝敗を判定する。
    - result: "ONGOING" / "VILLAGE_WIN" / "WOLF_WIN"
    - wolf_alive, village_alive: 生存数
    - reason: 簡単な説明
    ※ このAPIは Game.status を変更しない（判定のみ）。
    """
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    result = _judge_game_result(game_id, db)
    # 参考用に現在の status や day/night も返しておくと便利
    result.update(
        {
            "game_status": game.status,
            "curr_day": game.curr_day,
            "curr_night": game.curr_night,
        }
    )
    return result
