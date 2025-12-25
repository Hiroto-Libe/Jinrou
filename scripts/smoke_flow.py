#!/usr/bin/env python3
import json
import sys
import time
from urllib import request, error

BASE_URL = "http://127.0.0.1:8000"


def api(method, path, body=None):
    url = BASE_URL + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=10) as resp:
            payload = resp.read().decode("utf-8")
            return resp.status, json.loads(payload) if payload else None
    except error.HTTPError as e:
        payload = e.read().decode("utf-8")
        try:
            return e.code, json.loads(payload)
        except Exception:
            return e.code, {"detail": payload}
    except Exception as e:
        return 0, {"detail": str(e)}


def must_ok(status, data, label):
    if status < 200 or status >= 300:
        raise RuntimeError(f"{label} failed: {status} {data}")
    return data


def reset_and_seed(names):
    status, data = api(
        "POST",
        "/api/debug/reset_and_seed",
        {"player_names": names, "start_game": True},
    )
    data = must_ok(status, data, "reset_and_seed")
    return data["game_id"]


def make_names(prefix, count):
    return [f"{prefix}{i+1}" for i in range(count)]


def fetch_members(game_id):
    status, data = api("GET", f"/api/games/{game_id}/members")
    return must_ok(status, data, "members")


def fetch_game(game_id):
    status, data = api("GET", f"/api/games/{game_id}")
    return must_ok(status, data, "game")


def fetch_judge(game_id):
    status, data = api("GET", f"/api/games/{game_id}/judge")
    return must_ok(status, data, "judge")


def day_vote(game_id, voter_id, target_id):
    status, data = api(
        "POST",
        f"/api/games/{game_id}/day_vote",
        {"voter_member_id": voter_id, "target_member_id": target_id},
    )
    return status, data


def resolve_day(game_id, requester_id):
    status, data = api(
        "POST",
        f"/api/games/{game_id}/resolve_day_simple",
        {"requester_member_id": requester_id},
    )
    return status, data


def wolf_vote(game_id, wolf_id, target_id):
    status, data = api(
        "POST",
        f"/api/games/{game_id}/wolves/vote",
        {
            "wolf_member_id": wolf_id,
            "target_member_id": target_id,
            "priority_level": 1,
        },
    )
    return status, data


def knight_guard(game_id, knight_id, target_id):
    status, data = api(
        "POST",
        f"/api/games/{game_id}/knight/{knight_id}/guard",
        {"target_member_id": target_id},
    )
    return status, data


def resolve_night(game_id):
    status, data = api("POST", f"/api/games/{game_id}/resolve_night_simple", {})
    return status, data


def day_vote_status(game_id):
    status, data = api("GET", f"/api/games/{game_id}/day_vote_status")
    return must_ok(status, data, "day_vote_status")


def set_game_members(game_id, updates):
    status, data = api(
        "POST",
        "/api/debug/set_game_members",
        {"game_id": game_id, "updates": updates, "reset_votes": True},
    )
    return must_ok(status, data, "set_game_members")


def reveal_roles(game_id):
    status, data = api("GET", f"/api/games/{game_id}/reveal_roles")
    return must_ok(status, data, "reveal_roles")


def set_reveal_roles(game_id, requester_id, enabled):
    status, data = api(
        "POST",
        f"/api/games/{game_id}/reveal_roles",
        {"requester_member_id": requester_id, "enabled": enabled},
    )
    return status, data


def host_member(members):
    for m in members:
        if m.get("order_no") == 1:
            return m
    return members[0]


def by_role(members, role_type):
    return [m for m in members if m.get("role_type") == role_type and m.get("alive", True)]


def village_like(members):
    return [m for m in members if m.get("role_type") != "WEREWOLF" and m.get("alive", True)]


def pick_village_target(members, exclude_ids=None):
    exclude_ids = set(exclude_ids or [])
    for m in members:
        if m.get("role_type") == "WEREWOLF":
            continue
        if m["id"] in exclude_ids:
            continue
        if m.get("alive", True):
            return m["id"]
    return None


def pick_wolf_target(members):
    for m in members:
        if m.get("role_type") == "WEREWOLF" and m.get("alive", True):
            return m["id"]
    return None


def set_roles(game_id, members, wolves_count, knight=False, seer=False, madman=False, medium=False):
    total = len(members)
    specials = sum(1 for x in [knight, seer, madman, medium] if x)
    max_wolves = total - specials
    if max_wolves < 1:
        raise RuntimeError("not enough members for roles")
    wolves_count = min(wolves_count, max_wolves)
    if wolves_count < 1:
        raise RuntimeError("wolves_count too small")

    assigned = set()
    updates = []
    ordered = members[:]

    # wolves
    for m in ordered:
        if len(assigned) >= wolves_count:
            break
        assigned.add(m["id"])
        updates.append({"member_id": m["id"], "role_type": "WEREWOLF", "team": "WOLF", "alive": True})

    # specials
    def add_special(role_type, team):
        for m in ordered:
            if m["id"] in assigned:
                continue
            assigned.add(m["id"])
            updates.append({"member_id": m["id"], "role_type": role_type, "team": team, "alive": True})
            return
        raise RuntimeError(f"not enough members for {role_type}")

    if knight:
        add_special("KNIGHT", "VILLAGE")
    if seer:
        add_special("SEER", "VILLAGE")
    if medium:
        add_special("MEDIUM", "VILLAGE")
    if madman:
        add_special("MADMAN", "WOLF")

    # rest villagers
    for m in ordered:
        if m["id"] in assigned:
            continue
        updates.append({"member_id": m["id"], "role_type": "VILLAGER", "team": "VILLAGE", "alive": True})

    set_game_members(game_id, updates)
    return refresh_members(game_id)


def alive_ids(members):
    return [m["id"] for m in members if m.get("alive", True)]


def is_wolf(m):
    return m.get("role_type") == "WEREWOLF"


def can_day_vote(voter, target):
    if voter["id"] == target["id"]:
        return False
    if is_wolf(voter) and is_wolf(target):
        return False
    if not target.get("alive", True):
        return False
    return True


def find_member(members, mid):
    for m in members:
        if m["id"] == mid:
            return m
    return None


def find_fallback_target(voter, members, exclude_ids=None):
    exclude_ids = set(exclude_ids or [])
    for m in members:
        if not m.get("alive", True):
            continue
        if m["id"] == voter["id"]:
            continue
        if m["id"] in exclude_ids:
            continue
        if is_wolf(voter) and is_wolf(m):
            continue
        return m["id"]
    return None


def vote_all_for_target(game_id, members, target_id):
    target = find_member(members, target_id)
    if not target:
        raise RuntimeError("target not found")
    for voter in members:
        if not voter.get("alive", True):
            continue
        if can_day_vote(voter, target):
            status, data = day_vote(game_id, voter["id"], target_id)
            must_ok(status, data, "day_vote")
            continue
        fallback_id = find_fallback_target(voter, members, exclude_ids=[target_id])
        if not fallback_id:
            raise RuntimeError("no fallback target for day_vote")
        status, data = day_vote(game_id, voter["id"], fallback_id)
        must_ok(status, data, "day_vote fallback")


def cast_votes_to_targets(game_id, members, target_ids):
    voters = [m for m in members if m.get("alive", True)]
    if len(target_ids) != len(voters):
        raise RuntimeError("target_ids length must match alive voters")
    remaining = list(target_ids)
    for voter in voters:
        picked_idx = None
        for i, tid in enumerate(remaining):
            target = find_member(members, tid)
            if not target:
                continue
            if can_day_vote(voter, target):
                picked_idx = i
                break
        if picked_idx is None:
            raise RuntimeError("no valid target for voter")
        tid = remaining.pop(picked_idx)
        status, data = day_vote(game_id, voter["id"], tid)
        must_ok(status, data, "day_vote assigned")


def refresh_members(game_id):
    return fetch_members(game_id)


def print_case(title):
    print(f"\n=== {title} ===")


def ensure_status(game_id, expected):
    game = fetch_game(game_id)
    status = game.get("status")
    if status != expected:
        raise RuntimeError(f"expected status {expected}, got {status}")


def case_runoff(player_count):
    print_case("runoff")
    game_id = reset_and_seed(make_names("A", player_count))
    members = fetch_members(game_id)
    members = set_roles(game_id, members, wolves_count=2)
    host = host_member(members)
    vlike = village_like(members)
    if len(vlike) < 4:
        raise RuntimeError("not enough village-like for runoff")

    n = len([m for m in members if m.get("alive", True)])
    top_count = n // 3
    remainder = n - top_count * 3

    main_candidates = [vlike[0]["id"], vlike[1]["id"], vlike[2]["id"]]
    extra_candidates = [m["id"] for m in vlike[3:3 + remainder]]

    targets = []
    for cid in main_candidates:
        targets.extend([cid] * top_count)
    for cid in extra_candidates:
        targets.append(cid)

    if len(targets) != n:
        raise RuntimeError("failed to build runoff targets")

    cast_votes_to_targets(game_id, members, targets)

    status, data = resolve_day(game_id, host["id"])
    data = must_ok(status, data, "resolve_day")
    if data.get("status") != "RUNOFF":
        raise RuntimeError(f"expected RUNOFF, got {data}")

    st = day_vote_status(game_id)
    if not st.get("is_runoff"):
        raise RuntimeError("expected is_runoff true")

    runoff_candidates = st.get("candidate_ids") or []
    if len(runoff_candidates) < 2:
        raise RuntimeError("not enough runoff candidates")
    cand_a = runoff_candidates[0]
    cand_b = runoff_candidates[1]

    # runoff: everyone except cand_a votes cand_a; cand_a votes cand_b
    for m in members:
        if not m.get("alive", True):
            continue
        target = cand_a if m["id"] != cand_a else cand_b
        status, data = day_vote(game_id, m["id"], target)
        must_ok(status, data, "day_vote runoff")

    status, data = resolve_day(game_id, host["id"])
    data = must_ok(status, data, "resolve_day runoff")
    print("runoff ok")


def case_wolf_win(player_count):
    print_case("wolf win by night")
    game_id = reset_and_seed(make_names("G", player_count))
    members = fetch_members(game_id)
    wolves_needed = (player_count - 2 + 1) // 2
    members = set_roles(game_id, members, wolves_count=wolves_needed)
    host = host_member(members)
    wolves = by_role(members, "WEREWOLF")
    vlike = village_like(members)
    if not wolves or len(vlike) < 2:
        raise RuntimeError("not enough roles for wolf win case")

    day_target = vlike[0]["id"]
    vote_all_for_target(game_id, members, day_target)

    status, data = resolve_day(game_id, host["id"])
    data = must_ok(status, data, "resolve_day")
    game = fetch_game(game_id)
    if game.get("status") == "FINISHED":
        judge = fetch_judge(game_id)
        if judge.get("result") != "WOLF_WIN":
            raise RuntimeError(f"expected WOLF_WIN, got {judge}")
        print("wolf win ok")
        return
    ensure_status(game_id, "NIGHT")

    members = refresh_members(game_id)
    vlike = village_like(members)
    night_target = vlike[0]["id"]
    for w in wolves:
        status, data = wolf_vote(game_id, w["id"], night_target)
        must_ok(status, data, "wolf_vote")

    status, data = resolve_night(game_id)
    data = must_ok(status, data, "resolve_night")
    judge = fetch_judge(game_id)
    if judge.get("result") != "WOLF_WIN":
        raise RuntimeError(f"expected WOLF_WIN, got {judge}")
    print("wolf win ok")


def case_village_win_and_host_dead(player_count):
    print_case("host dead can resolve")
    game_id = reset_and_seed(make_names("H", player_count))
    members = fetch_members(game_id)
    members = set_roles(game_id, members, wolves_count=2)
    host = host_member(members)

    # day 1: execute host
    vote_all_for_target(game_id, members, host["id"])

    status, data = resolve_day(game_id, host["id"])
    data = must_ok(status, data, "resolve_day")
    game = fetch_game(game_id)
    if game.get("status") == "FINISHED":
        judge = fetch_judge(game_id)
        if judge.get("result") != "WOLF_WIN":
            raise RuntimeError(f"expected WOLF_WIN, got {judge}")
        print("wolf win ok")
        return
    ensure_status(game_id, "NIGHT")

    # night: wolves attack any village-like to move to day 2
    members = refresh_members(game_id)
    wolves = by_role(members, "WEREWOLF")
    vlike = village_like(members)
    if not wolves or not vlike:
        raise RuntimeError("roles missing after day 1")

    night_target = vlike[0]["id"]
    for w in wolves:
        status, data = wolf_vote(game_id, w["id"], night_target)
        must_ok(status, data, "wolf_vote")
    status, data = resolve_night(game_id)
    data = must_ok(status, data, "resolve_night")
    ensure_status(game_id, "DAY_DISCUSSION")

    # day 2: execute a wolf if possible (vote target = first wolf)
    members = refresh_members(game_id)
    wolves = by_role(members, "WEREWOLF")
    if not wolves:
        raise RuntimeError("no wolves left to execute")
    target = wolves[0]["id"]
    vote_all_for_target(game_id, members, target)

    # host is dead but must be able to resolve
    status, data = resolve_day(game_id, host["id"])
    data = must_ok(status, data, "resolve_day by dead host")
    if data.get("status") not in ("NIGHT", "VILLAGE_WIN", "WOLF_WIN"):
        raise RuntimeError(f"unexpected status after resolve: {data}")
    print("host dead resolve ok")


def case_knight_guard_success(player_count):
    print_case("knight guard success")
    game_id = reset_and_seed(make_names("K", player_count))
    members = fetch_members(game_id)
    members = set_roles(game_id, members, wolves_count=2, knight=True)
    host = host_member(members)
    knight = by_role(members, "KNIGHT")
    if not knight:
        raise RuntimeError("knight not found")
    knight_id = knight[0]["id"]

    # day 1: execute a non-knight village-like to enter night
    day_target = pick_village_target(members, exclude_ids=[knight_id])
    if not day_target:
        raise RuntimeError("no village target for day 1")
    vote_all_for_target(game_id, members, day_target)
    status, data = resolve_day(game_id, host["id"])
    data = must_ok(status, data, "resolve_day")
    game = fetch_game(game_id)
    if game.get("status") == "FINISHED":
        judge = fetch_judge(game_id)
        if judge.get("result") != "WOLF_WIN":
            raise RuntimeError(f"expected WOLF_WIN, got {judge}")
        print("wolf win ok")
        return
    ensure_status(game_id, "NIGHT")

    members = refresh_members(game_id)
    wolves = by_role(members, "WEREWOLF")
    if not wolves:
        raise RuntimeError("wolves not found")

    # wolves target someone, knight guards same target
    night_target = pick_village_target(members, exclude_ids=[knight_id])
    if not night_target:
        raise RuntimeError("no night target")
    for w in wolves:
        status, data = wolf_vote(game_id, w["id"], night_target)
        must_ok(status, data, "wolf_vote")
    status, data = knight_guard(game_id, knight_id, night_target)
    must_ok(status, data, "knight_guard")

    status, data = resolve_night(game_id)
    data = must_ok(status, data, "resolve_night")
    if not data.get("guarded_success"):
        raise RuntimeError(f"expected guard success, got {data}")
    print("guard success ok")


def case_day2_wolf_win(player_count):
    print_case("day2 wolf win")
    game_id = reset_and_seed(make_names("W", player_count))
    members = fetch_members(game_id)
    wolves_needed = (player_count - 2 + 1) // 2
    members = set_roles(game_id, members, wolves_count=wolves_needed, knight=True)
    host = host_member(members)
    knight = by_role(members, "KNIGHT")
    if not knight:
        raise RuntimeError("knight not found")
    knight_id = knight[0]["id"]
    wolves = by_role(members, "WEREWOLF")
    vlike = village_like(members)
    if not wolves or not vlike:
        raise RuntimeError("roles missing")

    # day 1: execute a village-like (not knight)
    day_target = pick_village_target(members, exclude_ids=[knight_id])
    if not day_target:
        raise RuntimeError("no village target")
    vote_all_for_target(game_id, members, day_target)
    status, data = resolve_day(game_id, host["id"])
    data = must_ok(status, data, "resolve_day")
    game = fetch_game(game_id)
    if game.get("status") == "FINISHED":
        judge = fetch_judge(game_id)
        if judge.get("result") != "WOLF_WIN":
            raise RuntimeError(f"expected WOLF_WIN, got {judge}")
        print("wolf win ok")
        return
    ensure_status(game_id, "NIGHT")

    # night 1: wolf kill to move toward wolf win
    members = refresh_members(game_id)
    wolves = by_role(members, "WEREWOLF")
    night_target = pick_village_target(members, exclude_ids=[knight_id])
    for w in wolves:
        status, data = wolf_vote(game_id, w["id"], night_target)
        must_ok(status, data, "wolf_vote")
    status, data = resolve_night(game_id)
    must_ok(status, data, "resolve_night")
    game = fetch_game(game_id)
    if game.get("status") == "FINISHED":
        judge = fetch_judge(game_id)
        if judge.get("result") != "WOLF_WIN":
            raise RuntimeError(f"expected WOLF_WIN, got {judge}")
        print("wolf win ok")
        return
    ensure_status(game_id, "DAY_DISCUSSION")

    # day2+ until wolf win
    for _ in range(5):
        members = refresh_members(game_id)
        day_target = pick_village_target(members, exclude_ids=[knight_id])
        if not day_target:
            break
        vote_all_for_target(game_id, members, day_target)
        status, data = resolve_day(game_id, host["id"])
        data = must_ok(status, data, "resolve_day")
        judge = fetch_judge(game_id)
        if judge.get("result") == "WOLF_WIN":
            print("wolf win ok")
            return
        game = fetch_game(game_id)
        if game.get("status") == "FINISHED":
            judge = fetch_judge(game_id)
            if judge.get("result") != "WOLF_WIN":
                raise RuntimeError(f"expected WOLF_WIN, got {judge}")
            print("wolf win ok")
            return
        ensure_status(game_id, "NIGHT")

        members = refresh_members(game_id)
        wolves = by_role(members, "WEREWOLF")
        if not wolves:
            break
        night_target = pick_village_target(members, exclude_ids=[knight_id])
        for w in wolves:
            status, data = wolf_vote(game_id, w["id"], night_target)
            must_ok(status, data, "wolf_vote")
        status, data = resolve_night(game_id)
        must_ok(status, data, "resolve_night")
        ensure_status(game_id, "DAY_DISCUSSION")
    raise RuntimeError("expected WOLF_WIN by day loop")


def case_day2_village_win(player_count):
    print_case("day2 village win")
    game_id = reset_and_seed(make_names("V", player_count))
    members = fetch_members(game_id)
    members = set_roles(game_id, members, wolves_count=2, knight=True)
    host = host_member(members)
    knight = by_role(members, "KNIGHT")
    if not knight:
        raise RuntimeError("knight not found")
    knight_id = knight[0]["id"]

    wolves = by_role(members, "WEREWOLF")

    # day 1: execute a wolf
    day1_target = wolves[0]["id"]
    vote_all_for_target(game_id, members, day1_target)
    status, data = resolve_day(game_id, host["id"])
    data = must_ok(status, data, "resolve_day")
    game = fetch_game(game_id)
    if game.get("status") == "FINISHED":
        judge = fetch_judge(game_id)
        if judge.get("result") != "WOLF_WIN":
            raise RuntimeError(f"expected WOLF_WIN, got {judge}")
        print("spectator result ready ok")
        return
    ensure_status(game_id, "NIGHT")

    # night 1: guard success to avoid night win
    members = refresh_members(game_id)
    wolves = by_role(members, "WEREWOLF")
    if not wolves:
        raise RuntimeError("no wolves for day2")
    night_target = pick_village_target(members, exclude_ids=[knight_id])
    for w in wolves:
        status, data = wolf_vote(game_id, w["id"], night_target)
        must_ok(status, data, "wolf_vote")
    status, data = knight_guard(game_id, knight_id, night_target)
    must_ok(status, data, "knight_guard")
    status, data = resolve_night(game_id)
    must_ok(status, data, "resolve_night")
    ensure_status(game_id, "DAY_DISCUSSION")

    # day2+ until village win (wolves executed each day, guard to avoid night loss)
    for _ in range(5):
        members = refresh_members(game_id)
        wolf_target = pick_wolf_target(members)
        if not wolf_target:
            break
        vote_all_for_target(game_id, members, wolf_target)
        status, data = resolve_day(game_id, host["id"])
        data = must_ok(status, data, "resolve_day")
        judge = fetch_judge(game_id)
        if judge.get("result") == "VILLAGE_WIN":
            print("village win ok")
            return
        ensure_status(game_id, "NIGHT")

        members = refresh_members(game_id)
        wolves = by_role(members, "WEREWOLF")
        if not wolves:
            break
        night_target = pick_village_target(members, exclude_ids=[knight_id])
        for w in wolves:
            status, data = wolf_vote(game_id, w["id"], night_target)
            must_ok(status, data, "wolf_vote")
        status, data = knight_guard(game_id, knight_id, night_target)
        must_ok(status, data, "knight_guard")
        status, data = resolve_night(game_id)
        must_ok(status, data, "resolve_night")
        ensure_status(game_id, "DAY_DISCUSSION")
    raise RuntimeError("expected VILLAGE_WIN by day loop")


def case_reveal_roles_shared(player_count):
    print_case("reveal roles shared")
    game_id = reset_and_seed(make_names("R", player_count))
    members = fetch_members(game_id)
    members = set_roles(game_id, members, wolves_count=2)
    host = host_member(members)
    non_host = members[1]["id"]

    status, data = set_reveal_roles(game_id, non_host, True)
    if status != 403:
        raise RuntimeError("expected 403 for non-host reveal")

    status, data = set_reveal_roles(game_id, host["id"], True)
    must_ok(status, data, "set_reveal_roles host on")
    state = reveal_roles(game_id)
    if not state.get("enabled"):
        raise RuntimeError("expected reveal_roles enabled")

    status, data = set_reveal_roles(game_id, host["id"], False)
    must_ok(status, data, "set_reveal_roles host off")
    state = reveal_roles(game_id)
    if state.get("enabled"):
        raise RuntimeError("expected reveal_roles disabled")
    print("reveal roles ok")


def case_spectator_result_ready(player_count):
    print_case("spectator result ready")
    game_id = reset_and_seed(make_names("S", player_count))
    members = fetch_members(game_id)
    wolves_needed = (player_count - 2 + 1) // 2
    members = set_roles(game_id, members, wolves_count=wolves_needed)
    host = host_member(members)
    vlike = village_like(members)
    if not vlike:
        raise RuntimeError("no village-like members")

    # day 1: execute a village-like to create a dead member
    day_target = vlike[0]["id"]
    vote_all_for_target(game_id, members, day_target)
    status, data = resolve_day(game_id, host["id"])
    data = must_ok(status, data, "resolve_day")
    game = fetch_game(game_id)
    if game.get("status") == "FINISHED":
        judge = fetch_judge(game_id)
        if judge.get("result") != "WOLF_WIN":
            raise RuntimeError(f"expected WOLF_WIN, got {judge}")
        print("spectator result ready ok")
        return
    ensure_status(game_id, "NIGHT")

    # night: wolves kill another village-like to reach WOLF_WIN
    members = refresh_members(game_id)
    wolves = by_role(members, "WEREWOLF")
    vlike = village_like(members)
    if not wolves or not vlike:
        raise RuntimeError("roles missing")
    night_target = vlike[0]["id"]
    for w in wolves:
        status, data = wolf_vote(game_id, w["id"], night_target)
        must_ok(status, data, "wolf_vote")
    status, data = resolve_night(game_id)
    data = must_ok(status, data, "resolve_night")
    judge = fetch_judge(game_id)
    if judge.get("result") != "WOLF_WIN":
        raise RuntimeError(f"expected WOLF_WIN, got {judge}")

    members = refresh_members(game_id)
    dead = [m for m in members if not m.get("alive", True)]
    if not dead:
        raise RuntimeError("expected at least one dead member")
    print("spectator result ready ok")


def main():
    for count in range(7, 16):
        print(f"\n######## players={count} ########")
        case_runoff(count)
        case_wolf_win(count)
        case_village_win_and_host_dead(count)
        case_reveal_roles_shared(count)
        case_knight_guard_success(count)
        case_day2_wolf_win(count)
        case_day2_village_win(count)
        case_spectator_result_ready(count)

    print("\nALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
