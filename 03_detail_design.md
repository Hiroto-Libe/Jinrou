# 🐺 人狼Webアプリ 詳細設計書

## 1. アーキテクチャ構成
- REST API：FastAPI
- WebSocket：FastAPI WebSocket
- DB：SQLite（SQLAlchemy ORM）
- ディレクトリ構成：  
  `app/main.py`, `app/api/v1/`, `app/ws/`, `app/models/`, `app/schemas/`

---

## 2. DB 詳細構成（ERまとめ）

### 2.1 マスタ
- `role_types`（役職マスタ）

### 2.2 台帳（永続）
- `profiles`  
  - 顔写真アイコン／表示名  
  - 削除は is_deleted=1

### 2.3 部屋構成
- `rooms`  
- `room_roster`（台帳→部屋の出席簿）  
- `room_members`（当日参加者）

### 2.4 ゲーム構成
- `games`（設定／状態／日数／VoteRound）  
- `game_members`（役職／生死／表示名のスナップショット）

### 2.5 夜アクション
- `wolf_votes`（priority_level + point）  
- `seer_actions`  
- `knight_actions`  
- `villager_suspicions`

### 2.6 昼行動
- `day_votes`  
- `executions`  
- `night_deaths`  
- `medium_reveals`  
- `phase_logs`

---

## 3. REST API 詳細設計

### 3.1 `/api/profiles`
- POST: 新規登録（顔写真URL/名前）
- GET: 一覧取得（active_only）
- DELETE: ソフトデリート

### 3.2 `/api/upload/avatar`
- multipartで画像アップロード
- 返却：`avatar_url`, `w`, `h`

### 3.3 `/api/rooms`
- POST: 部屋作成
- GET: 部屋一覧

### 3.4 `/api/rooms/{room_id}/roster`
- POST: 台帳プロフィールを出席簿へ追加
- GET: 出席簿一覧

### 3.5 `/api/rooms/{room_id}/members/bulk_from_roster`
- 出席簿→当日メンバーへスナップショット

### 3.6 `/api/games`
- POST: ゲーム開始
- POST `/role_assign`: 役職自動割り振り

---

## 4. WebSocket 詳細設計

### 4.1 接続
- `/ws?room_id=&game_id=&client_id=`
- C→S: `hello`
- S→C: `welcome`, `state_snapshot`

### 4.2 ホスト操作
- フェーズ遷移：`host_phase`
- 投票開始：`open_vote`
- 決選開始：`open_runoff`

### 4.3 夜アクション
- 人狼：`wolf_vote` → 狼全体へ `wolf_tally`
- 占い：`seer_action` → 朝に本人へ `seer_result`
- 騎士：`knight_action`
- 村人：`villager_suspicion`

### 4.4 投票アクション
- `vote_cast`
- `vote_tallied`
- `executed`
- 決選：`open_runoff`

### 4.5 結果
- `win_checked`
- `game_result`

---

## 5. ビジネスロジック詳細

### 5.1 夜の人狼処理
1. 全狼の `wolf_vote` が揃うまで朝へ遷移不可
2. 集計（sum of points）
3. 最大ポイント者が襲撃対象
4. 同点はランダム

### 5.2 騎士
- 自分護衛不可
- 連続護衛不可

### 5.3 投票
- `day_votes` に voter/day/round ごとに UNIQUE
- 同数 → 決選
- 3回同数 → ホスト決定 or ランダム決定

### 5.4 勝敗判定
- 人狼ゼロ → 村勝利
- 狼数 >= 村人数 → 狼勝利

---

## 6. 画面ワイヤー詳細

### 6.1 参加者：
- 登録
- 部屋待機
- 役職表示
- 夜アクション
- 朝
- 昼（議論タイマー）
- 投票
- 決選
- 結果

### 6.2 ホスト：
- 出席簿管理
- 当日参加者選択
- ゲーム設定
- 夜進行（狼投票進捗表示）
- 昼進行
- 投票管理
- 決選管理
- 処刑・勝敗表示

---

## 7. エラー扱い

### 7.1 REST／WS共通エラーフォーマット

```json
{
  "type": "error",
  "payload": {
    "code": "INVALID_PHASE",
    "message": "現在のフェーズでは操作できません"
  }
}
```

### 7.2 主なエラー

INVALID_PHASE
INVALID_TARGET
WOLVES_NOT_READY
DUPLICATE_VOTE
UNAUTHORIZED
IMAGE_TOO_LARGE

---

## 8. 今後の拡張

自動進行（タイマーによるフェーズ遷移）
狂人・狐などの追加役職
観戦モード
戦績・履歴
CDNでの画像ホスティング

---