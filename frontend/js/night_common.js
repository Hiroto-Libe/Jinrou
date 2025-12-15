// frontend/js/night_common.js
(function (global) {
  const API_BASE = "/api";

  function getQueryParams() {
    return new URLSearchParams(location.search);
  }

  function setText(el, msg) {
    if (el) el.textContent = msg ?? "";
  }

  function appendLog(resultEl, msg, type) {
    if (!resultEl) return;
    const div = document.createElement("div");
    if (type === "error") div.classList.add("error");
    if (type === "success") div.classList.add("success");
    div.textContent = msg;
    resultEl.appendChild(div);
  }

  async function fetchMe(gameId, playerId) {
    const url = `${API_BASE}/games/${encodeURIComponent(
      gameId
    )}/me?player_id=${encodeURIComponent(playerId)}`;
    const res = await fetch(url);
    if (!res.ok)
      throw new Error(`自分情報の取得に失敗しました (${res.status})`);
    return await res.json();
  }

  async function fetchMembers(gameId) {
    const res = await fetch(
      `${API_BASE}/games/${encodeURIComponent(gameId)}/members`
    );
    if (!res.ok)
      throw new Error(`プレイヤー一覧の取得に失敗しました (${res.status})`);
    return await res.json();
  }

  function defaultRenderMembers({
    members,
    me,
    containerEl,
    expectedRole,
    actionDone,
    onSelect,
    cardClass = "member-card",
  }) {
    if (!containerEl) return;
    containerEl.innerHTML = "";
    if (!Array.isArray(members)) return;

    const selfId = me?.player_id || me?.game_member_id;

    members.forEach((m) => {
      const card = document.createElement("div");
      card.className = cardClass;
      card.dataset.memberId = m.id;

      const isAlive =
        m.is_alive !== undefined ? m.is_alive : m.alive !== false;
      const isSelf = selfId && m.id === selfId;
      const roleMismatch = expectedRole && me?.role !== expectedRole;

      if (!isAlive) card.classList.add("dead");
      if (isSelf) card.classList.add("self");

      const displayName = m.display_name || m.name || `プレイヤー ${m.id}`;
      card.textContent = displayName;

      if (!isAlive || isSelf || actionDone || roleMismatch) {
        card.style.pointerEvents = "none";
      } else {
        card.addEventListener("click", () => {
          if (actionDone) return;
          containerEl
            .querySelectorAll("." + cardClass)
            .forEach((el) => el.classList.remove("selected"));
          card.classList.add("selected");
          onSelect(m);
        });
      }

      containerEl.appendChild(card);
    });
  }

  async function initNightRolePage(config) {
    const params = getQueryParams();
    const gameId = params.get("game_id");
    const playerId = params.get("player_id");

    const statusEl = document.getElementById(config.elements.statusId);
    const membersEl = document.getElementById(config.elements.membersId);
    const buttonEl = document.getElementById(config.elements.buttonId);
    const resultEl = document.getElementById(config.elements.resultId);

    if (!gameId || !playerId) {
      alert("game_id または player_id が指定されていません。URL を確認してください。");
      return;
    }

    let me = null;
    let members = [];
    let selectedTarget = null;
    let actionDone = false;

    function safeSetStatus(msg) {
      setText(statusEl, msg);
    }

    function disableAllCards() {
      if (!membersEl) return;
      membersEl
        .querySelectorAll(".member-card, .attack-card")
        .forEach((el) => (el.style.pointerEvents = "none"));
    }

    function markDone(message) {
      if (message) appendLog(resultEl, message, "success");
      safeSetStatus(config.texts.doneStatus || "今夜の行動は完了しました。");
      actionDone = true;
      disableAllCards();
      if (buttonEl) {
        buttonEl.disabled = true;
        buttonEl.style.display = "none";
      }
    }

    function findNameById(id) {
      if (!id || !Array.isArray(members)) return null;
      const m = members.find((x) => x.id === id);
      return m ? (m.display_name || m.name || null) : null;
    }

    async function sendAction() {
      if (!selectedTarget || !me) return;

      if (buttonEl) buttonEl.disabled = true;
      safeSetStatus("送信中です...");

      try {
        const endpoint = config.buildEndpoint(gameId, me);
        const body = config.buildRequestBody({ me, targetMember: selectedTarget });

        const res = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });

        if (!res.ok) {
          let errJson = null;
          let detail = "";

          try {
            errJson = await res.json();
            detail = errJson?.detail ?? "";
          } catch (_) {}

          // “済み系” は「完了扱い」
          if (res.status === 400 && detail === "Seer already inspected someone this night") {
            markDone("今夜の占いはすでに完了しています。");
            return;
          }
          if (res.status === 400 && detail === "Knight already guarded someone this night") {
            markDone("今夜の護衛はすでに完了しています。");
            return;
          }

          const raw = errJson ? JSON.stringify(errJson) : await res.text();
          throw new Error(`アクションに失敗しました (${res.status}): ${raw}`);
        }

        const data = await res.json();
        const msg = config.buildSuccessMessage({ data, targetMember: selectedTarget });

        appendLog(resultEl, msg, "success");
        safeSetStatus(config.texts.doneStatus || "この夜の行動は完了しました。");

        actionDone = true;
        disableAllCards();
        if (buttonEl) {
          buttonEl.disabled = true;
          buttonEl.style.display = "none";
        }
      } catch (err) {
        console.error(err);
        appendLog(resultEl, String(err), "error");
        safeSetStatus(`アクション送信でエラー: ${String(err).replace(/^Error:\s*/, "")}`);
        if (buttonEl) buttonEl.disabled = false;
      }
    }

    if (buttonEl) {
      buttonEl.addEventListener("click", sendAction);
      buttonEl.disabled = true;
      buttonEl.style.display = ""; // 初期状態は表示（done判定で非表示にする）
    }

    try {
      safeSetStatus(config.texts.loadingMe || "プレイヤー情報を読み込み中...");
      me = await fetchMe(gameId, playerId);

      // 役職ミスマッチは最初から操作不可
      if (config.expectedRole && me.role !== config.expectedRole) {
        appendLog(
          resultEl,
          config.texts.roleMismatch || "役職が異なるため、この画面からは操作できません。",
          "error"
        );
        safeSetStatus("この画面はあなたの役職には対応していません。");
        actionDone = true;
        disableAllCards();
        if (buttonEl) buttonEl.disabled = true;
        return;
      }

      // ✅ 事前「済み」チェック（あれば）
      let doneInfo = null;
      if (typeof config.checkAlreadyDone === "function") {
        doneInfo = await config.checkAlreadyDone({ gameId, me });
      }

      safeSetStatus(config.texts.loadingGame || "プレイヤー一覧を取得中...");
      members = await fetchMembers(gameId);

      // メンバー描画（done でも描画だけはして、選択不可にする）
      const renderFn = config.renderMembers || defaultRenderMembers;
      renderFn({
        members,
        me,
        containerEl: membersEl,
        expectedRole: config.expectedRole,
        actionDone: !!doneInfo?.done, // ← doneなら最初から選択不可
        onSelect: (m) => {
          selectedTarget = m;
          if (buttonEl) {
            buttonEl.disabled = false;
            buttonEl.style.display = ""; // 通常時は表示
          }
        },
      });

      if (doneInfo?.done) {
        // target_member_id があれば名前に変換して表示
        const tid = doneInfo.target_member_id;
        const tname = findNameById(tid);
        const msg = tname
          ? `${doneInfo.message || "今夜の行動はすでに完了しています。"}（対象：${tname}）`
          : (doneInfo.message || "今夜の行動はすでに完了しています。");

        markDone(msg);
        return;
      }

      // 通常時
      safeSetStatus(config.texts.selectPrompt || "対象を選択してください。");
    } catch (err) {
      console.error(err);
      appendLog(resultEl, String(err), "error");
      safeSetStatus("画面の初期化に失敗しました。URL やゲーム状態を確認してください。");
      if (buttonEl) buttonEl.disabled = true;
    }
  }

  global.JinrouNight = { initNightRolePage };
})(window);

// ===== Win/Lose auto redirect =====
async function redirectIfFinished(game_id, player_id) {
  const res = await fetch(`/api/games/${game_id}/judge`);
  if (!res.ok) return; // judge が落ちてもゲーム進行は止めない

  const data = await res.json(); // { result: "ONGOING" | "VILLAGE_WIN" | "WOLF_WIN" }
  if (data.result && data.result !== "ONGOING") {
    const qs = new URLSearchParams({ game_id, player_id });
    location.href = `/frontend/result.html?${qs.toString()}`;
  }
}

// ページ読み込み時に呼ぶ用（例外で落ちないように）
function setupAutoResultRedirect(game_id, player_id) {
  redirectIfFinished(game_id, player_id).catch(() => {});
}
