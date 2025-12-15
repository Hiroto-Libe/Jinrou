// /frontend/js/flow.js
(function (global) {
  function qs() {
    return new URLSearchParams(location.search);
  }

  function mustParam(name) {
    const v = qs().get(name);
    if (!v) throw new Error(`${name} がURLにありません`);
    return v;
  }

  async function fetchGame(gameId) {
    const res = await fetch(`/api/games/${encodeURIComponent(gameId)}`);
    if (!res.ok) throw new Error(`game取得失敗(${res.status})`);
    return await res.json();
  }

  // /api/games/{id}/me を使って role を取る（すでに安定動作している前提）
  async function fetchMe(gameId, playerId) {
    const res = await fetch(
      `/api/games/${encodeURIComponent(gameId)}/me?player_id=${encodeURIComponent(playerId)}`
    );
    if (!res.ok) throw new Error(`me取得失敗(${res.status})`);
    return await res.json();
  }

  function buildUrl(path, gameId, playerId) {
    return `/frontend/${path}?game_id=${encodeURIComponent(gameId)}&player_id=${encodeURIComponent(playerId)}`;
  }

  function nightPageByRole(role) {
    // role は /me の role（seer / knight / werewolf など）に合わせる
    // もし "SEER" など大文字ならここを揃える
    const r = String(role || "").toLowerCase();
    if (r === "werewolf") return "night_wolf_attack.html";
    if (r === "seer") return "seer_night.html";
    if (r === "knight") return "knight_night.html";
    return "night_wait.html";
  }

  async function gotoCurrentPhase({ replace = true } = {}) {
    const gameId = mustParam("game_id");
    const playerId = mustParam("player_id");

    const game = await fetchGame(gameId);

    // status 名はあなたの実装に合わせる（例: "NIGHT", "DAY", "MORNING"）
    const status = String(game.status || "").toUpperCase();

    let dest = null;

    if (status === "NIGHT") {
      const me = await fetchMe(gameId, playerId);
      dest = nightPageByRole(me.role);
    } else if (status === "DAY") {
      dest = "day.html";
    } else if (status === "MORNING") {
      dest = "morning.html";
    } else {
      // 想定外はとりあえず role_confirm へ
      dest = "role_confirm.html";
    }

    const url = buildUrl(dest, gameId, playerId);

    // 同じページなら遷移しない（ループ防止）
    if (location.pathname.endsWith(dest)) return;

    if (replace) location.replace(url);
    else location.href = url;
  }

  // 状態変化を待つ（ポーリング）
  async function watchPhase({ intervalMs = 1500 } = {}) {
    const gameId = mustParam("game_id");
    let prev = null;

    setInterval(async () => {
      try {
        const g = await fetchGame(gameId);
        const cur = String(g.status || "").toUpperCase();
        if (prev && prev !== cur) {
          // statusが変わったら現在フェーズへ自動遷移
          await gotoCurrentPhase({ replace: true });
        }
        prev = cur;
      } catch (e) {
        console.warn(e);
      }
    }, intervalMs);
  }

  global.JinrouFlow = { gotoCurrentPhase, watchPhase };
})(window);
