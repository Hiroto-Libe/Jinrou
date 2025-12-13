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

  async function fetchGame(gameId) {
    const url = `${API_BASE}/games/${encodeURIComponent(gameId)}`;
    const res = await fetch(url);
    if (!res.ok)
      throw new Error(`ゲーム情報の取得に失敗しました (${res.status})`);
    return await res.json();
  }

  // デフォルトのメンバー描画（必要なら各画面側で renderMembers を上書き）
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

  /**
   * 夜フェーズ共通初期化
   *
   * config:
   *  - expectedRole: 'seer' | 'knight' | 'wolf' など
   *  - elements: { statusId, membersId, buttonId, resultId }
   *  - buildEndpoint: (gameId, me) => string
   *  - buildRequestBody: ({ me, targetMember }) => any
   *  - buildSuccessMessage: ({ data, targetMember }) => string
   *  - texts: { loadingMe, loadingGame, selectPrompt, roleMismatch, doneStatus }
   *  - renderMembers (任意)
   *       ({ members, me, containerEl, expectedRole, actionDone, onSelect }) => void
   */
  async function initNightRolePage(config) {
    const params = getQueryParams();
    const gameId = params.get("game_id");
    const playerId = params.get("player_id");

    const statusEl = document.getElementById(config.elements.statusId);
    const membersEl = document.getElementById(config.elements.membersId);
    const buttonEl = document.getElementById(config.elements.buttonId);
    const resultEl = document.getElementById(config.elements.resultId);

    if (!gameId || !playerId) {
      alert(
        "game_id または player_id が指定されていません。URL を確認してください。"
      );
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

    async function sendAction() {
      if (!selectedTarget || !me) return;

      buttonEl.disabled = true;
      safeSetStatus("送信中です...");

      try {
        // ★ ここが重要：me も渡す
        const endpoint = config.buildEndpoint(gameId, me);
        const body = config.buildRequestBody({
          me,
          targetMember: selectedTarget,
        });

        const res = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });

        if (!res.ok) {
          const errText = await res.text();
          throw new Error(
            `アクションに失敗しました (${res.status}): ${errText}`
          );
        }

        const data = await res.json();
        const msg = config.buildSuccessMessage({
          data,
          targetMember: selectedTarget,
        });

        appendLog(resultEl, msg, "success");
        safeSetStatus(
          config.texts.doneStatus || "この夜の行動は完了しました。"
        );

        actionDone = true;
        disableAllCards();
      } catch (err) {
        console.error(err);
        appendLog(resultEl, String(err), "error");
        safeSetStatus(
          `アクション送信でエラー: ${String(err).replace(/^Error:\s*/, "")}`
        );
        buttonEl.disabled = false;
      }
    }

    if (buttonEl) {
      buttonEl.addEventListener("click", sendAction);
      buttonEl.disabled = true;
    }

    // 起動時フロー
    try {
      safeSetStatus(config.texts.loadingMe || "プレイヤー情報を読み込み中...");
      me = await fetchMe(gameId, playerId);

      if (config.expectedRole && me.role !== config.expectedRole) {
        appendLog(
          resultEl,
          config.texts.roleMismatch ||
            "役職が異なるため、この画面からは操作できません。",
          "error"
        );
        safeSetStatus("この画面はあなたの役職には対応していません。");
        if (buttonEl) buttonEl.disabled = true;
        actionDone = true;
      }

      safeSetStatus(
        config.texts.loadingGame || "プレイヤー一覧を読み込み中..."
      );

      const resMembers = await fetch(
        `${API_BASE}/games/${encodeURIComponent(gameId)}/members`
      );
      if (!resMembers.ok) {
        throw new Error(
          `プレイヤー一覧の取得に失敗しました (${resMembers.status})`
        );
      }

      members = await resMembers.json();

      const renderFn = config.renderMembers || defaultRenderMembers;

      renderFn({
        members,
        me,
        containerEl: membersEl,
        expectedRole: config.expectedRole,
        actionDone,
        onSelect: (m) => {
          selectedTarget = m;
          if (buttonEl) buttonEl.disabled = false;
        },
      });

      if (!actionDone) {
        safeSetStatus(
          config.texts.selectPrompt || "対象を選択してください。"
        );
      }
    } catch (err) {
      console.error(err);
      appendLog(resultEl, String(err), "error");
      safeSetStatus(
        "画面の初期化に失敗しました。URL やゲーム状態を確認してください。"
      );
      if (buttonEl) buttonEl.disabled = true;
    }
  }

  global.JinrouNight = {
    initNightRolePage,
  };
})(window);
