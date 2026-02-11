# 02 仕様検討書（Specification）

## 1. 目的

`01_requirements.md` をもとに、現時点の実装コード（FastAPI + frontend HTML/JS）に合わせた機能仕様を定義する。  
本書は「利用者視点の挙動」と「システム仕様」の中間レベルを扱う。

## 2. 対象範囲

- 対象:
  - ルーム作成、参加登録、当日メンバー確定
  - ゲーム間のメンバ追加/削除
  - Room削除
  - ゲーム作成、開始、昼夜進行、勝敗判定
  - 参加者の待機画面から役職画面への自動遷移
  - QRによる参加URL共有
- 対象外（将来対応）:
  - WebSocket によるリアルタイム通知
  - 顔写真撮影/アップロードの正式実装
  - 認証/権限管理

## 3. システム構成

- バックエンド: FastAPI (`app/`)
- フロントエンド: 静的HTML/JS (`frontend/`)
- DB: SQLite
- APIプレフィックス: `/api`
- フロント配信: `/frontend/*` （FastAPI StaticFiles）

## 4. 利用者と責務

- GM（司会）
  - Room作成、参加導線共有
  - roster確認、members確定
  - Game作成、Start、進行操作
- 参加者
  - `room_join` で名前登録
  - 開始まで待機
  - 開始検出後、自動で `role_confirm` に遷移

## 5. 画面仕様

## 5.1 `room_create.html`（GM）

- ルーム作成
  - Room名入力（任意）
  - Room作成ボタン
- 参加導線共有
  - 参加URL表示
  - 参加URLのQR表示
  - URLコピー/開く
- roster管理
  - roster更新
  - `bulk_from_roster` 実行（6人以上で有効）
- ゲーム開始
  - Game作成
  - 同じメンバで次ゲーム作成（GMトリガー）
  - 開始者（GM）選択
  - Start
  - 必要時 role_assign
- メンバ編集
  - games の合間に members 追加/削除
  - 進行中ゲーム中は編集不可
- Room管理
  - Room削除（関連データも削除）
- 監視表示
  - 参加者一覧は表示
  - 役職は非表示

## 5.2 `room_join.html`（参加者）

- `room_id` クエリ必須
- 名前登録（roster追加）
- 登録後は待機状態
- 2秒ポーリングで以下を検出
  - `room.current_game_id`
  - 自分の `room_member_id`
  - `game.status`（および取得可能なら `game.started`）
- `current_game_id` が更新された場合は、新しいゲーム待機へ自動追従
- 開始検出時に `role_confirm.html?game_id=...&player_id=...` へ自動遷移

## 6. 業務フロー仕様

1. GMがRoom作成
2. 参加者がQRから `room_join` へ入り、名前登録
3. GMがrosterを確認し、`bulk_from_roster` で当日メンバー確定
4. GMがGame作成
5. GMが開始者を選んでStart
6. 参加者が待機画面から `role_confirm` へ自動遷移
7. 昼夜進行（投票、夜行動、解決）
8. 勝敗確定で終了
9. GMが必要に応じて「同じメンバで次ゲーム作成」を実行
10. 参加者は `room_join` 待機のまま新しい `current_game_id` を検出し、Start後に再度自動遷移

## 7. 役職・陣営仕様

`decide_roles(n)` に準拠:

- 6人: 狼2 / 占1 / 騎1 / 狂1 / 村1
- 7人: 狼2 / 占1 / 騎1 / 狂1 / 村2
- 8人以上: 狼2 / 占1 / 騎1 / 狂1 / 霊1 / 村1 + 追加村人

陣営:

- WOLF: `WEREWOLF`, `MADMAN`
- VILLAGE: それ以外

## 8. ゲーム進行仕様

- `start` 実行後
  - 役職未設定なら自動割当
  - `started = true`
  - `status = DAY_DISCUSSION`
- 昼
  - `day_vote` で投票
  - `resolve_day_simple`
    - 最多得票者を処刑
    - 同票は候補からランダムで1名処刑
    - 勝敗未決なら `status = NIGHT`
- 夜
  - 狼投票（重み付き）
  - 占い/騎士/霊媒
  - `resolve_night_simple`
    - 襲撃対象確定（同点ランダム）
    - 騎士護衛成功時は死亡なし
    - 勝敗未決なら `status = DAY_DISCUSSION`
- 勝敗判定
  - 生存狼陣営数（狂人含む）と村陣営数で判定

## 9. API仕様（主要）

## 9.1 Rooms

- `POST /api/rooms`
- `DELETE /api/rooms/{room_id}`
- `GET /api/rooms/{room_id}`
- `POST /api/rooms/{room_id}/roster`
- `GET /api/rooms/{room_id}/roster`
- `POST /api/rooms/{room_id}/members/bulk_from_roster`
- `GET /api/rooms/{room_id}/members`
- `POST /api/rooms/{room_id}/members`
- `DELETE /api/rooms/{room_id}/members/{member_id}`

## 9.2 Games

- `POST /api/games`
- `POST /api/games/{game_id}/role_assign`
- `POST /api/games/{game_id}/start`
- `GET /api/games/{game_id}`
- `GET /api/games/{game_id}/members`
- `POST /api/games/{game_id}/day_vote`
- `POST /api/games/{game_id}/resolve_day_simple`
- `POST /api/games/{game_id}/wolves/vote`
- `POST /api/games/{game_id}/resolve_night_simple`

## 10. データ永続化仕様

- Room: `rooms`
- roster: `room_roster`
- 当日参加: `room_members`
- Game: `games`
- GameMember: `game_members`
- 投票/夜行動:
  - `day_votes`, `wolf_votes`, `seer_inspects`, `medium_inspects`, `knight_guards`

## 11. エラー仕様（代表）

- `404 Room not found / Game not found`
- `400 Game is not in NIGHT phase / DAY_DISCUSSION phase`
- `400 Member is not a werewolf`
- `400 Need at least 6 players`
- `400 Cannot modify members while current game is in progress`

## 12. 非機能仕様（現状）

- スマホ画面対応（レスポンシブ）
- 同一LAN運用を想定
- 認証なし（URL共有ベース）
- HTTPS/本番デプロイは環境依存

## 13. 要件との差分

- `01_requirements.md` 記載の WebSocket リアルタイム同期は未実装（現状はポーリング）
- 顔写真撮影・管理の正式UXは未実装（Profile APIは存在）
- MVPとして手動進行中心の設計は要件どおり
