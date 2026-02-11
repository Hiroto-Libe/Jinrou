# 03 詳細設計書（Detailed Design）

## 1. 目的

`02_specification.md` の内容を、実装可能な粒度で設計に落とし込む。  
対象は現行コードベース（`app/`, `frontend/`, `tests/`）とする。

## 2. 全体アーキテクチャ

## 2.1 構成要素

- APIサーバ: FastAPI
- 永続層: SQLite + SQLAlchemy ORM
- フロント: 静的HTML + Vanilla JS
- テスト: pytest + TestClient

## 2.2 配置

- APIエントリ: `app/main.py`
- ルーティング: `app/api/v1/__init__.py`
- 機能別API:
  - `app/api/v1/rooms.py`
  - `app/api/v1/games.py`
  - `app/api/v1/profiles.py`
  - `app/api/v1/debug.py`
- 画面:
  - `frontend/room_create.html`
  - `frontend/room_join.html`
  - `frontend/role_confirm.html` ほか

## 2.3 起動時処理

`app/main.py`:

- `Base.metadata.create_all(bind=engine)`
- `ensure_room_members_schema()`
- CORS設定（開発用）
- `/frontend` 静的配信
- `/api` ルータ登録

## 3. データモデル設計

## 3.1 Room系

- `rooms`
  - `id` (PK)
  - `name`
  - `owner_profile_id` (nullable)
  - `current_game_id` (nullable)
- `room_roster`
  - 参加表明リスト
  - `room_id`, `profile_id`, `alias_name`, `joined_at`
- `room_members`
  - 当日確定メンバー
  - `display_name`, `avatar_url`, `is_host`

## 3.2 Profile系

- `profiles`
  - `display_name`, `avatar_url`, `note`
  - `is_deleted`（ソフトデリート）

## 3.3 Game系

- `games`
  - `status`, `started`
  - `curr_day`, `curr_night`
  - ルール設定値（dayタイマー、狼投票ポイント等）
  - `seer_first_white_target_id`
  - `last_executed_member_id`
- `game_members`
  - `room_member_id` を参照
  - `role_type`, `team`, `alive`, `order_no`
- 行動ログ
  - `wolf_votes`
  - `day_votes`
  - `seer_inspects`
  - `knight_guards`
  - `medium_inspects`

## 4. API詳細設計

## 4.1 Rooms API

`app/api/v1/rooms.py`

- `POST /rooms`
  - 入力: `RoomCreate`
  - 出力: `RoomOut`
- `POST /rooms/{room_id}/roster`
  - 入力: `display_name`
  - 処理: Profile新規作成 -> RoomRoster登録
- `POST /rooms/{room_id}/members/bulk_from_roster`
  - 処理: rosterから `room_members` を生成
  - 先頭生成者に `is_host = true` を付与
- `POST /rooms/{room_id}/members`
  - 手動メンバ追加
  - 進行中ゲーム中は拒否
- `DELETE /rooms/{room_id}/members/{member_id}`
  - 手動メンバ削除
  - 進行中ゲーム中は拒否
- `GET /rooms/{room_id}`
  - `current_game_id` を返す（join画面の自動遷移検出で使用）
- `DELETE /rooms/{room_id}`
  - Room削除
  - 関連する games / game_members / votes / night actions も削除

## 4.2 Games API

`app/api/v1/games.py`

- `POST /games`
  - `rooms.current_game_id` を更新
  - `game_members` を生成（`room_members` 由来）
- `POST /games/{game_id}/role_assign`
  - 役職割当 (`decide_roles`)
  - `status = ROLE_ASSIGN`
- `POST /games/{game_id}/start`
  - 必要時 role/team 自動割当
  - `started = true`
  - `status = DAY_DISCUSSION`
  - `curr_day = 1`, `curr_night = 0`
- `POST /games/{game_id}/day_vote`
  - 昼投票登録/更新
- `POST /games/{game_id}/resolve_day_simple`
  - 投票集計
  - 同票はランダム処刑
  - 勝敗判定後、継続なら `status = NIGHT`
- `POST /games/{game_id}/wolves/vote`
  - 夜の狼投票（priorityに応じた重み）
- `POST /games/{game_id}/resolve_night_simple`
  - 夜明け処理
  - 護衛判定
  - 勝敗判定後、継続なら `status = DAY_DISCUSSION`

## 4.3 Profiles API

`app/api/v1/profiles.py`

- 作成/取得/一覧/削除（ソフトデリート）

## 4.4 Debug API

`app/api/v1/debug.py`

- `reset_and_seed`: 開発用初期化
- `set_game_members`: 役職/生死/票リセットの強制更新

## 5. フロントエンド詳細設計

## 5.1 `room_create.html`

### ローカル状態

- `roomId`, `roomName`, `gameId`, `bulkDone`, `startMemberId`
- `localStorage` で保持

### 主要処理

- Room作成
- 参加URL生成
- QR描画
  - `qrcode` ライブラリ利用
  - 読み込み失敗時は `api.qrserver.com` へフォールバック
- roster更新/確定
- game作成/start
- 同一メンバで次ゲーム作成（`POST /api/games` を再実行）
- games の合間に members 追加/削除
- Room削除
- 監視表示（参加者一覧、役職は表示しない）

### URL再開

- `room_create.html?room_id=...` を受け取り、別端末で同一Roomを再開可能

## 5.2 `room_join.html`

### ローカル状態

- `room_id`（クエリ）
- `name`, `joined`, `roomMemberId`, `gameId`（localStorage）

### 主要処理

- 名前登録（rosterへPOST）
- 2秒ポーリング
  - Room名/roster表示更新
  - `current_game_id` 検出
  - `current_game_id` 更新時に新ゲームへ追従（旧 `game_id` 固定を避ける）
  - `room_members` から自分のID特定
  - `game.status`（および取得可能なら `started`）で開始判定
- 開始検出後:
  - `role_confirm` へ自動遷移
  - 終了状態（`FINISHED` / `WOLF_WIN` / `VILLAGE_WIN`）は待機継続

### 入力安定化

- IME変換中のEnter誤送信防止
- ポーリング中の入力上書き防止

## 6. 状態遷移設計

## 6.1 Game.status 遷移

- 初期: `WAITING`
- 任意: `ROLE_ASSIGN`（手動割当時）
- 開始: `DAY_DISCUSSION`
- 昼解決後:
  - 継続: `NIGHT`
  - 終了: 勝敗状態（`WOLF_WIN` / `VILLAGE_WIN`）相当
- 夜解決後:
  - 継続: `DAY_DISCUSSION`
  - 終了: 勝敗状態相当

## 6.2 参加者画面遷移

- `room_join`（未参加）
- `room_join`（待機）
- `role_confirm`（自動遷移）
- （次ゲーム作成後）`room_join`（新ゲーム待機） -> `role_confirm`（再遷移）

## 7. 判定ロジック設計

## 7.1 役職配布

- `decide_roles(n)` で人数別テンプレートを返却
- `team` は `WEREWOLF`, `MADMAN` を WOLF として設定

## 7.2 勝敗判定

- 生存メンバーのみ対象
- `team == WOLF` を狼陣営数として集計（狂人含む）
- 判定:
  - 狼0 -> `VILLAGE_WIN`
  - 狼 >= 村 -> `WOLF_WIN`
  - それ以外 -> `ONGOING`

## 8. エラーハンドリング設計

- 404: リソース不存在（Room/Game/Profile等）
- 400: フェーズ不整合、入力不足、人数不足
- 400: 進行中ゲーム中の members 編集要求
- 403: Host権限不足（例: day解決）

フロントは `toJson` でレスポンスを吸収し、画面内ログで表示する。

## 9. テスト設計

- テストフレームワーク: pytest
- API単体 + フローを中心に検証
- 現在の自動テスト結果: `68 passed`

主な検証観点:

- Room/roster/members
- start/role_assign
- day_vote/resolve_day
- wolves vote/resolve_night
- seer/knight/medium
- madmanを含む勝敗判定
- ゲーム間の members 追加/削除
- 進行中ゲームでの members 編集禁止
- Room削除時の関連データ削除

## 10. 既知の制約と今後課題

- WebSocket未実装（現状はポーリング）
- 認証/権限分離は未実装
- 同名プレイヤーがいる場合、`room_join` の room_member 解決は曖昧になる可能性あり
- CORSは開発用途の限定設定のみ
- SQLite前提のため本番高負荷運用には制限あり

## 11. 運用手順（推奨）

1. `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
2. GMが `room_create` を開く
3. 参加者はQRから `room_join` に入って登録
4. GMが `roster確定 -> Game作成 -> Start`
5. 参加者が自動遷移したことを確認し、ゲーム進行
6. ゲーム終了後、GMが `同じメンバで次ゲーム作成` を押下
7. 参加者は `room_join` で待機継続し、Start後に再度自動遷移
