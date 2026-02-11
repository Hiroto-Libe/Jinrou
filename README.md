# Jinrou - Web人狼ゲーム（FastAPI + HTML/JS）

FastAPI + SQLite + HTML/Vanilla JS で構成された、スマホ参加型の Web 人狼ゲームです。  
現時点の実運用は、**Room作成 -> 参加者登録 -> GM開始 -> 参加者端末が自動で役職確認へ遷移** を前提としています。

## 概要

- バックエンド: FastAPI (`app/`)
- フロントエンド: HTML/CSS/Vanilla JS (`frontend/`)
- DB: SQLite (`werewolf.db`)
- テスト: pytest (`tests/`)

## 現在のゲームフロー（実装済み）

1. GM が `room_create` でルームを作成
2. 参加者は参加URL（またはQR）から `room_join` にアクセスして名前登録
3. GM が `roster` を確認して `bulk_from_roster` で当日メンバー確定
4. GM が `Game作成` -> `Start`
5. 参加者は `room_join` の待機画面から `role_confirm` へ自動遷移
6. 以後は昼夜フェーズを進行
7. ゲーム終了後、GM は同じメンバで次ゲームを作成して再開可能
8. ゲーム間に GM がメンバ追加/削除を実施可能

## 画面一覧（主要）

- `frontend/room_create.html`  
  - GM向け画面
  - 参加URL表示、QR表示、roster確認、Game作成/開始
  - 同じメンバで次ゲーム作成（GMトリガー）
  - ゲーム間のメンバ追加/削除
  - Room削除
  - 参加者監視表示は役職を出さない運用
- `frontend/room_join.html`  
  - 参加者向け登録/待機画面
  - 名前登録後は待機し、開始検出後に `role_confirm` へ自動遷移
  - `current_game_id` 更新を検出し、次ゲーム待機へ自動追従
- `frontend/role_confirm.html`  
  - 個人の役職確認画面
- `frontend/day.html` / `frontend/morning.html` / `frontend/night_*.html` / `frontend/result.html`  
  - 各フェーズのプレイ画面

## 役職構成（現実装）

`app/api/v1/games.py` の `decide_roles` に基づく構成:

- 6人: 狼2 / 占1 / 騎1 / 狂1 / 村1
- 7人: 狼2 / 占1 / 騎1 / 狂1 / 村2
- 8人以上: 狼2 / 占1 / 騎1 / 狂1 / 霊1 / 村1 + 追加分は村人

陣営判定:

- 狼陣営: `WEREWOLF`, `MADMAN`
- 村陣営: 上記以外

## 起動方法（ローカル）

### 1) 仮想環境を有効化

```bash
source .venv313/bin/activate
```

### 2) APIサーバを起動

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## アクセス方法

- GM（ホスト）: `http://<PCのIP>:8000/frontend/room_create.html`
- 参加者: GM が表示した参加URL or QR から `room_join` へ

同一LANでの利用を想定:

- PC とスマホは同じ Wi-Fi に接続
- QR のURLは `127.0.0.1` ではなく `PCのIP` を使う

## 主要API（抜粋）

### Rooms

- `POST /api/rooms`
- `DELETE /api/rooms/{room_id}`
- `GET /api/rooms/{room_id}`
- `POST /api/rooms/{room_id}/roster`
- `GET /api/rooms/{room_id}/roster`
- `POST /api/rooms/{room_id}/members/bulk_from_roster`
- `GET /api/rooms/{room_id}/members`
- `POST /api/rooms/{room_id}/members`
- `DELETE /api/rooms/{room_id}/members/{member_id}`

### Games

- `POST /api/games`
- `POST /api/games/{game_id}/role_assign`
- `POST /api/games/{game_id}/start`
- `GET /api/games/{game_id}`
- `GET /api/games/{game_id}/members`

### Day/Night

- `POST /api/games/{game_id}/day_vote`
- `POST /api/games/{game_id}/resolve_day_simple`
- `POST /api/games/{game_id}/wolves/vote`
- `POST /api/games/{game_id}/resolve_night_simple`

## 自動テスト

```bash
source .venv313/bin/activate
pytest -q
```

最新確認結果:

- `68 passed`

## 最近の運用改善点

- `room_create` で参加URLのQR表示対応
- `room_join` で参加後待機 -> GM開始で自動遷移
- 同一メンバでの次ゲーム再開（GMトリガー）に対応
- ゲーム間メンバ編集（追加/削除）に対応
- Room削除（関連ゲームデータ含む）に対応
- GM監視画面で役職非表示
- 勝敗判定で `MADMAN` を狼陣営としてカウント
- 昼処理の同票時は候補から1名をランダム処刑

## トラブルシュート

- 参加者がQRを読んでも接続できない  
  - `uvicorn` を `--host 0.0.0.0` で起動しているか確認
  - QRのURLが `http://<PCのIP>:8000/...` になっているか確認
  - PC/スマホが同じWi-Fiか確認
- 画面が古い表示のまま  
  - ブラウザをハードリロード（Mac: `Cmd + Shift + R`）
- APIが起動しているか確認したい  
  - `http://127.0.0.1:8000` で `{"message":"Jinrou API is running"}` が返るか確認

## ディレクトリ構成

- `app/`  
  FastAPIアプリ本体（API, モデル, スキーマ）
- `frontend/`  
  画面HTML/CSS/JS
- `tests/`  
  pytest テストコード
- `scripts/`  
  スモークテストなどの補助スクリプト
- `Doc/`  
  要件・メモ類
