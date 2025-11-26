# 🐺 人狼Webアプリ 仕様検討書（更新版）
更新日: 2025-xx-xx

本ドキュメントは、既存対面人狼ゲームを Web アプリ化し、
スマホで役職行動・投票を行えるシステムの仕様をまとめる。

本版では以下を更新：
- 霊媒師の夜結果取得仕様の追加
- 狂人（MADMAN）の追加
- フェーズ構成と FastAPI 実装の整合性調整
- 役職構成の人数別仕様更新

---

# 1. フェーズ構成（更新）

本アプリ実装は既存の複雑フェーズを簡略化し、次のフェーズで動作する：

```
WAITING → ROLE_ASSIGN → NIGHT → DAWN_RESOLVE → MORNING
→ DAY → VOTE → TALLY → RUNOFF → EXECUTION
→ MEDIUM_REVEAL → WIN_CHECK → RESULT
```

内部処理：

- 夜明け処理：`resolve_night_simple`
- 昼決着処理：`resolve_day_simple`
- 勝敗判定：昼夜の決着後に自動実施

UI で利用するフェーズ名：

| フェーズ | 説明 |
|---------|------|
| WAITING | 待機、参加者選択 |
| ROLE_ASSIGN | 役職配布 |
| NIGHT | 人狼・占い師・騎士・霊媒師 行動時間 |
| DAY_DISCUSSION | 昼議論フェーズ |
| EXECUTION（内部） | 投票集計・追放 |
| VILLAGE_WIN / WOLF_WIN | ゲーム終了 |

---

# 2. 役職構成（狂人追加）

## 2.1 実装役職一覧

| 役職 | 英語名 | 陣営 | 能力 |
|------|--------|--------|------|
| 村人 | VILLAGER | VILLAGE | 能力なし |
| 人狼 | WEREWOLF | WOLF | 夜に襲撃投票 |
| 占い師 | SEER | VILLAGE | 夜に陣営判定 |
| 霊媒師 | MEDIUM | VILLAGE | 前日の処刑者の陣営判定 |
| 騎士 | KNIGHT | VILLAGE | 夜に護衛 |
| 狂人（NEW） | MADMAN | WOLF | 能力なし（村側偽装） |

10人例の基本構成：狼2/村4/占1/霊1/騎1/狂1
人数に応じて **自動で役職構成を割り振る**
---

## 2.2 狂人の仕様

- team = "WOLF"
- role_type = "MADMAN"
- 占い師・霊媒師から黒判定
- 人狼襲撃には参加しない
- 勝敗判定では狼陣営に加算

---

# 3. 夜フェーズ仕様

### 3.1 人狼（WEREWOLF）
- Lv1（絶対排除）：3pt  
- Lv2（強めに怪しい）：2pt  
- Lv3（なんとなく）：1pt
- 全狼が投票完了するまで朝へ進行不可
- ホストUIの「朝へ進む」ボタンは Disabled
- **無襲撃不可**
- 同点はランダム選出

### 3.2 占い師（SEER）
- 生存者1名を占う
- 初日白通知APIあり

### 3.3 騎士（KNIGHT）
- 生存者1名を護衛
- 自分護衛不可
- 連続護衛不可（設定変更可能）

### 3.4 霊媒師（MEDIUM）
- 夜に前日の処刑者の陣営を知る
- API: `/games/{game_id}/medium/{medium_member_id}/inspect`
- 1日1回のみ

### 3.5 狂人（MADMAN）
- 夜行動なし

### 3.6 村人（メタ対策）

- 夜に「怪しいと思う人」を1人選ぶ（ゲーム結果に影響なし）
---

# 4. 昼フェーズ仕様

- 昼議論時間は生存人数で可変（5→4→3分）
- 昼投票API：`day_vote`
- 決着処理：`resolve_day_simple`
- 処刑者IDを `game.last_executed_member_id` に保存

## 5. 投票

- 生存者から1人を選択
- 公開/非公開は設定で切替
- 同数なら決選 → 一人に絞れるまで繰り返す
- 3回連続同数 → ホスト決定 or ランダム強制

---

# 6. 勝敗条件（狂人反映）

- 生存狼陣営（WEREWOLF + MADMAN）が 0 → 村勝利
- 生存狼陣営 >= 生存村陣営 → 狼勝利

---

# 7. データ保存

- last_executed_member_id に処刑者IDを保持
- MediumInspect テーブルに霊媒結果を保存

---

# 8. 今後の拡張

- 狐・共有者追加
- 自動フェーズ遷移
- WebSocket 通知
- E2Eテスト追加

---
