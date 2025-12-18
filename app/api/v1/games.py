# app/api/v1/games.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
import uuid
import random 
from typing import List, Optional, Dict

from ...api.deps import get_db_dep
from ...models.room import Room, RoomMember
from ...models.game import (
    Game,
    GameMember,
    WolfVote,
    DayVote,
    SeerInspect,
    MediumInspect,   # ★ 追加
)
from ...models.knight import KnightGuard
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
from ...schemas.seer import (
    SeerFirstWhiteOut,
    SeerInspectCreate,
    SeerInspectOut,
)
from ...schemas.knight import (
    KnightGuardCreate,
    KnightGuardOut,
)
from ...schemas.medium import MediumInspectOut  # ★ 追加
from ...schemas.game_member import GameMemberMe
from pydantic import BaseModel

router = APIRouter(prefix="/games", tags=["games"])


# -----------------------------
# 🎮 ゲーム作成
# -----------------------------
@router.post("", response_model=GameOut)
def create_game(
    payload: GameCreate,
    db: Session = Depends(get_db_dep),
):
    # 部屋が存在するか確認
    room = db.get(Room, payload.room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="room not found")

    # 部屋メンバーを取得（順番付き）
    room_members = (
        db.query(RoomMember)
        .filter(RoomMember.room_id == room.id)
        .all()
    )
    if not room_members:
        raise HTTPException(status_code=400, detail="room has no members")

    # Game を作成
    game = Game(
        id=str(uuid.uuid4()),
        room_id=room.id,
        status="waiting",   # 必要なら初期ステータス
    )
    db.add(game)
    db.flush()             # game.id を使うので flush しておく

    room.current_game_id = game.id
    db.add(room) 

    # RoomMember から GameMember を作成
    for i, rm in enumerate(room_members, start=1):
        gm = GameMember(
            id=str(uuid.uuid4()),
            game_id=game.id,
            room_member_id=rm.id,
            display_name=rm.display_name,
            avatar_url=rm.avatar_url,
            role_type=None,     # 役職は別途付与するなら後で更新
            team=None,
            alive=True,
            order_no=i,         # ★ ここがポイント：order_in_room ではなく order_no
        )
        db.add(gm)

    db.commit()
    db.refresh(game)
    db.refresh(room)
    return game




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


# 中略（既存のエンドポイントたち）

@router.get("/{game_id}/day_timer")
def get_day_timer(
    game_id: str,
    db: Session = Depends(get_db_dep),
):
    """
    朝の議論タイマー秒数を返すAPI。

    仕様:
    - 基本値は game.day_timer_sec（例: 300秒）
    - 生存プレイヤー数が 4人のとき → 240秒
    - 生存プレイヤー数が 3人以下のとき → 180秒
    - それ以外（5人以上）のとき → 基本値そのまま
    """
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # 生存しているメンバー数をカウント
    alive_count = (
        db.query(func.count(GameMember.id))
        .filter(
            GameMember.game_id == game_id,
            GameMember.alive == True,
        )
        .scalar()
    )

    base = game.day_timer_sec  # 基本値（例: 300秒）

    # 人数に応じた調整
    if alive_count <= 3:
        timer_sec = 180
    elif alive_count == 4:
        timer_sec = 240
    else:
        timer_sec = base

    return {
        "game_id": game.id,
        "curr_day": game.curr_day,
        "alive_count": int(alive_count),
        "base_timer_sec": base,
        "timer_sec": timer_sec,
    }


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


@router.post("/{game_id}/start", response_model=GameOut)
def start_game(
    game_id: str,
    db: Session = Depends(get_db_dep),
):
    # ゲーム取得
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # ★ ここから追加（司会チェック）
    host = (
        db.query(RoomMember)
          .filter(
              RoomMember.room_id == game.room_id,
              RoomMember.is_host == True,
          )
          .first()
    )
    if not host:
        raise HTTPException(status_code=400, detail="Host player not found")
    # ★ ここまで追加

    # すでに開始済みなら 400
    # → status ではなく started フラグで判定する
    if getattr(game, "started", False):
        raise HTTPException(status_code=400, detail="Game already started")

    # 参加メンバー取得（GameMember）
    members = (
        db.query(GameMember)
        .filter(GameMember.game_id == game_id)
        .order_by(GameMember.order_no.asc())
        .all()
    )
    if not members:
        raise HTTPException(status_code=400, detail="No members in game")

    n = len(members)
    if n < 6:
        # decide_roles の設計に合わせて下限6人にしておく（必要なら調整）
        raise HTTPException(status_code=400, detail="Need at least 6 players")

    # 人数に応じた役職構成を取得
    roles = decide_roles(n)  # [(role_type, team), ...] のリスト
    if len(roles) != n:
        raise HTTPException(status_code=500, detail="Role assignment mismatch")

    # ランダムに割り当てるためにシャッフル
    import random
    random.shuffle(roles)

    # メンバーに役職と陣営を付与
    for m, (role_type, team) in zip(members, roles):
        m.role_type = role_type   # 例: "WEREWOLF", "SEER", "VILLAGER", ...
        m.team = team             # 例: "WOLF" or "VILLAGE"
        db.add(m)

    # --- ゲーム開始フラグ & フェーズ設定 ---

    # started フラグを立てる（元の仕様どおり）
    game.started = True

    # ★ 開始は「昼」から
    game.status = "DAY_DISCUSSION"

    # ★ 昼1日目から開始、夜はまだ来ていない
    if hasattr(game, "curr_day"):
        game.curr_day = 1
    if hasattr(game, "curr_night"):
        game.curr_night = 0

    db.add(game)
    db.commit()
    db.refresh(game)
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

    # 👇 ここを修正：team だけチェックする
    if wolf.team != "WOLF":
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

    # 狂人(MADMAN)は team=WOLF だが、襲撃対象としては許可したいので
    # 「他の人狼(WEREWOLF)」だけ禁止にする
    if target.role_type == "WEREWOLF":
        raise HTTPException(status_code=400, detail="Wolf cannot target other werewolves")

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
    return WolfVoteOut.model_validate(vote, from_attributes=True)


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
    - 合計ポイント最大のターゲットを1人選ぶ
    - そのターゲットが騎士に護衛されていれば襲撃失敗（誰も死なない）
    - 護衛されていなければ、そのターゲットを死亡扱い（alive=False）
    - Game.status を DAY_DISCUSSION または FINISHED に更新
    - 処理後に勝敗判定も行う
    - 戻り値は killed_member_id / victim / guarded_success / game_result / status を含む dict
    """
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if game.status != "NIGHT":
        raise HTTPException(status_code=400, detail="Game is not in NIGHT phase")

    night_no = getattr(game, "curr_night", 1)

    votes: list[WolfVote] = (
        db.query(WolfVote)
        .filter(
            WolfVote.game_id == game_id,
            WolfVote.night_no == night_no,
        )
        .all()
    )

    # --- 投票なし → 誰も死なない ---
    if not votes:
        game_result = _judge_game_result(game_id, db)

        # ゲーム終了の場合のみ FINISHED にしておく（DB 上の状態）
        if game_result["result"] != "ONGOING":
            if hasattr(game, "status"):
                game.status = game_result["result"]   
            if hasattr(game, "result"):
                game.result = game_result["result"]
            if hasattr(game, "finished"):
                game.finished = True
            db.add(game)
            db.commit()

        # レスポンス用 status（テスト仕様）
        if game_result["result"] == "ONGOING":
            status_for_response = "DAY_DISCUSSION"
        else:
            status_for_response = game_result["result"]  # "WOLF_WIN" / "VILLAGE_WIN"

        return {
            "killed_member_id": None,
            "victim": None,
            "guarded_success": False,
            "game_result": game_result,
            "status": status_for_response,
        }

    # --- 投票ありパス ---

    # ターゲットごとにポイント集計
    points_by_target: dict[str, int] = {}
    for v in votes:
        pts = v.points_at_vote or 0
        points_by_target[v.target_member_id] = points_by_target.get(
            v.target_member_id, 0
        ) + pts

    # 一番ポイントが高いターゲットを決定
    targeted_member_id = max(points_by_target, key=points_by_target.get)

    # 騎士護衛があるかどうか
    guard = (
        db.query(KnightGuard)
        .filter(
            KnightGuard.game_id == game_id,
            KnightGuard.night_no == night_no,
            KnightGuard.target_member_id == targeted_member_id,
        )
        .one_or_none()
    )

    guarded_success = guard is not None
    killed_member_id: str | None = None
    victim_obj: GameMember | None = None

    if guarded_success:
        # 護衛成功 → 誰も死なない
        killed_member_id = None
    else:
        target = db.get(GameMember, targeted_member_id)
        if target and target.alive:
            target.alive = False
            db.add(target)
            victim_obj = target
            killed_member_id = target.id

    # 勝敗判定
    game_result = _judge_game_result(game_id, db)

    if game_result["result"] == "ONGOING":
        # ゲーム継続 → 昼議論へ
        game.status = "DAY_DISCUSSION"
        if hasattr(game, "curr_day"):
            game.curr_day = (game.curr_day or 0) + 1
    else:
        # ゲーム終了（DB 上は FINISHED）
        if hasattr(game, "status"):
            game.status = game_result["result"] 
        if hasattr(game, "result"):
            game.result = game_result["result"]
        if hasattr(game, "finished"):
            game.finished = True

    db.add(game)
    db.commit()

    # victim の dict 生成
    victim_dict = None
    if victim_obj is not None:
        db.refresh(victim_obj)
        victim_dict = {"id": victim_obj.id}

    # ✅ レスポンス用 status（テスト仕様に合わせる）
    if game_result["result"] == "ONGOING":
        status_for_response = "DAY_DISCUSSION"
    else:
        status_for_response = game_result["result"]  # "WOLF_WIN" / "VILLAGE_WIN"

    return {
        "killed_member_id": killed_member_id,
        "victim": victim_dict,
        "guarded_success": guarded_success,
        "game_result": game_result,
        "status": status_for_response,
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
        .order_by(GameMember.order_no.asc())
        .all()
    )

    # ★ ここで None を潰して Pydantic に渡す
    result: list[GameMemberOut] = []
    for m in members:
        role_type = m.role_type or "VILLAGER"
        team = m.team or "VILLAGE"

        result.append(
            GameMemberOut(
                id=m.id,
                game_id=m.game_id,
                room_member_id=m.room_member_id,
                display_name=m.display_name,
                avatar_url=m.avatar_url,
                role_type=role_type,
                team=team,
                alive=m.alive,
                order_no=m.order_no,
            )
        )

    return result


# -----------------------------
# 👥 人数に応じた役職構成
# -----------------------------
def decide_roles(n: int) -> list[tuple[str, str]]:
    """
    n人に対する役職構成を返す。
    戻り値: [(role_type, team), ...] * n

    役職:
      - VILLAGER
      - WEREWOLF
      - SEER
      - MEDIUM
      - KNIGHT
      - MADMAN  ← 狂人（狼陣営・能力なし）
    """

    if n == 6:
        # 狼2 / 占1 / 騎1 / 村1 / 狂1
        base = [
            "WEREWOLF", "WEREWOLF",
            "SEER",
            "KNIGHT",
            "VILLAGER",
            "MADMAN",
        ]

    elif n == 7:
        # 狼2 / 占1 / 騎1 / 村2 / 狂1
        base = [
            "WEREWOLF", "WEREWOLF",
            "SEER",
            "KNIGHT",
            "VILLAGER", "VILLAGER",
            "MADMAN",
        ]

    elif n == 8:
        # 狼2 / 占1 / 霊1 / 騎1 / 村2 / 狂1
        base = [
            "WEREWOLF", "WEREWOLF",
            "SEER",
            "MEDIUM",
            "KNIGHT",
            "VILLAGER", "VILLAGER",
            "MADMAN",
        ]

    elif n == 9:
        # 狼2 / 占1 / 霊1 / 騎1 / 村3 / 狂1
        base = [
            "WEREWOLF", "WEREWOLF",
            "SEER",
            "MEDIUM",
            "KNIGHT",
            "VILLAGER", "VILLAGER", "VILLAGER",
            "MADMAN",
        ]

    elif n == 10:
        # 狼2 / 占1 / 霊1 / 騎1 / 村4 / 狂1
        base = [
            "WEREWOLF", "WEREWOLF",
            "SEER",
            "MEDIUM",
            "KNIGHT",
            "VILLAGER", "VILLAGER", "VILLAGER", "VILLAGER",
            "MADMAN",
        ]

    else:
        # デフォルト:
        #  - 狼 = max(2, n // 4)
        #  - SEER / MEDIUM / KNIGHT / MADMAN を1人ずつ
        #  - 残りは VILLAGER
        wolves = max(2, n // 4)
        base = ["WEREWOLF"] * wolves + ["SEER", "MEDIUM", "KNIGHT", "MADMAN"]
        while len(base) < n:
            base.append("VILLAGER")

    def to_team(role: str) -> str:
        # 狼陣営：WEREWOLF + MADMAN
        return "WOLF" if role in ("WEREWOLF", "MADMAN") else "VILLAGE"

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
    - 現在の `day_no` の投票を集計
    - 最多得票者を 1 人処刑（`alive = False`）
    - 同票ならランダムに 1 人を選ぶ
    - 昼の処刑後に **勝敗判定（judge_game_result）** を実施
        - 判定結果が `VILLAGE_WIN` / `WOLF_WIN` の場合  
            - `Game.status = "FINISHED"`  
            - `Game.result` に勝敗（`"VILLAGE_WIN"` / `"WOLF_WIN"`）を保存  
            - **夜フェーズには遷移しない**
        - 判定結果が `ONGOING` の場合のみ  
            - `Game.status = "NIGHT"` に遷移  
            - `curr_day`, `curr_night` をインクリメント
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

    # 昼の処刑反映
    victim.alive = False
    db.add(victim)

    # この昼に処刑されたプレイヤーを記録
    game.last_executed_member_id = victim.id
    db.add(game)
    db.commit()
    db.refresh(victim)
    db.refresh(game)

    # ★ 昼の処刑後に勝敗判定
    judge = _judge_game_result(game.id, db)

    if judge["result"] != "ONGOING":
        # 村人勝利 or 人狼勝利 → 夜には遷移せず終了
        game.status = "FINISHED"
        # ゲーム結果として保持（必要なら）
        if hasattr(game, "result"):
            game.result = judge["result"]  # "VILLAGE_WIN" or "WOLF_WIN"
        if hasattr(game, "finished"):
            game.finished = True

        db.add(game)
        db.commit()
        db.refresh(game)

        next_status = judge["result"]  # レスポンスとしては勝敗をそのまま返す
    else:
        # まだゲーム継続 → ここで初めて NIGHT へ進める
        game.status = "NIGHT"
        game.curr_day = game.curr_day + 1
        game.curr_night = game.curr_night + 1

        db.add(game)
        db.commit()
        db.refresh(game)

        next_status = "NIGHT"

    return {
        "game_id": game.id,
        "day_no": day_no,
        "status": next_status,  # "NIGHT" / "VILLAGE_WIN" / "WOLF_WIN"
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
    - まだ白通知ターゲットが決まっていなければ、人狼（WEREWOLF）以外からランダムに1人選び、
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
            GameMember.role_type != "WEREWOLF",  # 人狼以外は候補にする
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


@router.post(
    "/{game_id}/seer/{seer_member_id}/inspect",
    response_model=SeerInspectOut,
)
def seer_inspect(
    game_id: str,
    seer_member_id: str,
    data: SeerInspectCreate,
    db: Session = Depends(get_db_dep),
):
    """
    占い師の夜行動API:
    - ゲームが NIGHT のときのみ実行可能
    - seer_member_id は SEER 本人であること
    - 生存中であること
    - 1夜につき1回だけ
    - 対象は同じゲーム内の生存メンバー
    """
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if game.status != "NIGHT":
        raise HTTPException(status_code=400, detail="Game is not in NIGHT phase")

    # 占い師本人
    seer = db.get(GameMember, seer_member_id)
    if not seer or seer.game_id != game_id:
        raise HTTPException(status_code=404, detail="Seer member not found")

    if seer.role_type != "SEER":
        raise HTTPException(status_code=400, detail="This member is not SEER")

    if not seer.alive:
        raise HTTPException(status_code=400, detail="Dead seer cannot inspect")

    # 対象
    target = db.get(GameMember, data.target_member_id)
    if not target or target.game_id != game_id:
        raise HTTPException(status_code=404, detail="Target member not found")

    if not target.alive:
        raise HTTPException(status_code=400, detail="Target is already dead")

    if target.id == seer.id:
        raise HTTPException(status_code=400, detail="Seer cannot inspect themselves")

    night_no = game.curr_night

    # その夜はすでに占っていないか（1夜1回制限）
    existing = (
        db.query(SeerInspect)
        .filter(
            SeerInspect.game_id == game_id,
            SeerInspect.night_no == night_no,
            SeerInspect.seer_member_id == seer.id,
        )
        .one_or_none()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Seer already inspected someone this night",
        )

    # 判定ロジック：role_type が WEREWOLF のときだけ黒
    is_wolf = (target.role_type == "WEREWOLF")

    inspect = SeerInspect(
        id=str(uuid.uuid4()),
        game_id=game_id,
        night_no=night_no,
        seer_member_id=seer.id,
        target_member_id=target.id,
        is_wolf=is_wolf,
    )
    db.add(inspect)
    db.commit()
    db.refresh(inspect)

    return SeerInspectOut.model_validate(inspect, from_attributes=True)

class SeerInspectStatusOut(BaseModel):
    done: bool
    night_no: int
    target_member_id: str | None = None


@router.get(
    "/{game_id}/seer/{seer_member_id}/inspect/status",
    response_model=SeerInspectStatusOut,
)
def seer_inspect_status(
    game_id: str,
    seer_member_id: str,
    db: Session = Depends(get_db_dep),
):
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    seer = db.get(GameMember, seer_member_id)
    if not seer or seer.game_id != game_id:
        raise HTTPException(status_code=404, detail="Seer member not found")

    night_no = game.curr_night  # あなたの実装に合わせて（curr_nightでOKならそのまま）

    existing = (
        db.query(SeerInspect)
        .filter(
            SeerInspect.game_id == game_id,
            SeerInspect.night_no == night_no,
            SeerInspect.seer_member_id == seer_member_id,
        )
        .one_or_none()
    )

    return SeerInspectStatusOut(
        done=existing is not None,
        night_no=night_no,
        target_member_id=(existing.target_member_id if existing else None),
    )


@router.post(
    "/{game_id}/knight/{knight_member_id}/guard",
    response_model=KnightGuardOut,
)
def knight_guard(
    game_id: str,
    knight_member_id: str,
    data: KnightGuardCreate,
    db: Session = Depends(get_db_dep),
):
    """
    騎士の夜行動API:
    - ゲームが NIGHT のときのみ実行可能
    - KNIGHT 本人であること
    - 生存していること
    - 1夜につき1回だけ
    - self_guard / consecutive_guard の制約は Game 設定に従う
    """
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if game.status != "NIGHT":
        raise HTTPException(status_code=400, detail="Game is not in NIGHT phase")

    # 騎士本人
    knight = db.get(GameMember, knight_member_id)
    if not knight or knight.game_id != game_id:
        raise HTTPException(status_code=404, detail="Knight member not found")

    if knight.role_type != "KNIGHT":
        raise HTTPException(status_code=400, detail="This member is not KNIGHT")

    if not knight.alive:
        raise HTTPException(status_code=400, detail="Dead knight cannot guard")

    # 対象
    target = db.get(GameMember, data.target_member_id)
    if not target or target.game_id != game_id:
        raise HTTPException(status_code=404, detail="Target member not found")

    if not target.alive:
        raise HTTPException(status_code=400, detail="Target is already dead")

    # self_guard 制約
    if (not game.knight_self_guard) and target.id == knight.id:
        raise HTTPException(status_code=400, detail="Self guard is not allowed")

    night_no = game.curr_night

    # 連続ガード制約（同じ相手を連続で守る禁止）
    if not game.knight_consecutive_guard:
        last_guard = (
            db.query(KnightGuard)
            .filter(
                KnightGuard.game_id == game_id,
                KnightGuard.knight_member_id == knight.id,
                KnightGuard.night_no == night_no - 1,
            )
            .one_or_none()
        )
        if last_guard and last_guard.target_member_id == target.id:
            raise HTTPException(
                status_code=400,
                detail="Consecutive guard is not allowed for the same target",
            )

    # その夜にすでに護衛していないか
    existing = (
        db.query(KnightGuard)
        .filter(
            KnightGuard.game_id == game_id,
            KnightGuard.night_no == night_no,
            KnightGuard.knight_member_id == knight.id,
        )
        .one_or_none()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Knight already guarded someone this night",
        )

    guard = KnightGuard(
        id=str(uuid.uuid4()),
        game_id=game_id,
        night_no=night_no,
        knight_member_id=knight.id,
        target_member_id=target.id,
    )
    db.add(guard)
    db.commit()
    db.refresh(guard)

    return KnightGuardOut.model_validate(guard, from_attributes=True)

class KnightGuardStatusOut(BaseModel):
    done: bool
    night_no: int
    target_member_id: str | None = None


@router.get(
    "/{game_id}/knight/{knight_member_id}/guard/status",
    response_model=KnightGuardStatusOut,
)
def knight_guard_status(
    game_id: str,
    knight_member_id: str,
    db: Session = Depends(get_db_dep),
):
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # 騎士本人の最低限チェック（※UIのためなので軽めでOK。厳密にしたいならrole/aliveも確認）
    knight = db.get(GameMember, knight_member_id)
    if not knight or knight.game_id != game_id:
        raise HTTPException(status_code=404, detail="Knight member not found")

    night_no = game.curr_night

    existing = (
        db.query(KnightGuard)
        .filter(
            KnightGuard.game_id == game_id,
            KnightGuard.night_no == night_no,
            KnightGuard.knight_member_id == knight_member_id,
        )
        .one_or_none()
    )

    return KnightGuardStatusOut(
        done=existing is not None,
        night_no=night_no,
        target_member_id=(existing.target_member_id if existing else None),
    )


@router.post(
    "/{game_id}/medium/{medium_member_id}/inspect",
    response_model=MediumInspectOut,
)
def medium_inspect(
    game_id: str,
    medium_member_id: str,
    db: Session = Depends(get_db_dep),
):
    """
    霊媒師の夜行動API:
    - ゲームが NIGHT のときのみ実行可能
    - medium_member_id は MEDIUM 本人であること
    - 生存中であること
    - 直前の昼に処刑されたプレイヤーの陣営を知る
    - 1日につき1回だけ（同じ day_no では複数回不可）
    """
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if game.status != "NIGHT":
        raise HTTPException(status_code=400, detail="Game is not in NIGHT phase")

    # 霊媒師本人
    medium = db.get(GameMember, medium_member_id)
    if not medium or medium.game_id != game_id:
        raise HTTPException(status_code=404, detail="Medium member not found")

    if medium.role_type != "MEDIUM":
        raise HTTPException(status_code=400, detail="This member is not MEDIUM")

    if not medium.alive:
        raise HTTPException(status_code=400, detail="Dead medium cannot inspect")

    # 直前の昼に処刑されたプレイヤーがいるか？
    if not game.last_executed_member_id:
        raise HTTPException(status_code=400, detail="No executed member to inspect")

    executed = db.get(GameMember, game.last_executed_member_id)
    if not executed or executed.game_id != game_id:
        raise HTTPException(status_code=500, detail="Executed member not found")

    # この夜に対応する昼は 1 日前の curr_day
    day_no = game.curr_day - 1
    if day_no <= 0:
        raise HTTPException(status_code=400, detail="No previous day to inspect")

    # 同じ day_no で既に霊媒していないかチェック（1日1回制限）
    existing = (
        db.query(MediumInspect)
        .filter(
            MediumInspect.game_id == game_id,
            MediumInspect.day_no == day_no,
            MediumInspect.medium_member_id == medium.id,
        )
        .one_or_none()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Medium already inspected for this day",
        )

    # 判定ロジック：role_type が WEREWOLF のときだけ黒
    is_wolf = (executed.role_type == "WEREWOLF")

    inspect = MediumInspect(
        id=str(uuid.uuid4()),
        game_id=game_id,
        day_no=day_no,
        medium_member_id=medium.id,
        target_member_id=executed.id,
        is_wolf=is_wolf,
    )
    db.add(inspect)
    db.commit()
    db.refresh(inspect)

    return MediumInspectOut.model_validate(inspect, from_attributes=True)



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


ROLE_MAP = {
    "WEREWOLF": "wolf",
    "SEER": "seer",
    "KNIGHT": "knight",
    "MEDIUM": "medium",
    "MADMAN": "madman",
    "VILLAGER": "villager",
    None: "villager",  # 念のため
}

@router.get("/{game_id}/me", response_model=GameMemberMe)
def get_my_info(
    game_id: str,
    player_id: str,
    db: Session = Depends(get_db_dep),
) -> GameMemberMe:
    """
    実際の GameMember から自分の役職・状態を返す本番版。
    player_id は GameMember.id を想定。
    """
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    member = db.get(GameMember, player_id)
    if not member or member.game_id != game_id:
        raise HTTPException(status_code=404, detail="Member not found in this game")

    # role_type は "WEREWOLF" / "SEER" ... なので、フロント向けに小文字にマップする
    role_key = ROLE_MAP.get(member.role_type, "villager")
    status = "alive" if member.alive else "dead"

    return GameMemberMe(
        game_id=game.id,
        player_id=member.id,
        role=role_key,
        status=status,
    )
