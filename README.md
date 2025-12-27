# Jinrou - Web 人狼ゲーム（FastAPI）

本プロジェクトは **FastAPI + SQLite + SQLAlchemy + Pydantic v2** を用いて構築した  
「複数人がスマホから参加できる Web 人狼ゲーム」です。  
UI は HTML/CSS/Vanilla JS の実装版で、**役職ごとに画面が分かれます**。

---

# 🚀 特徴

- **役職ごとに見える画面が異なる Web 人狼アプリ**
- **URLベース参加（認証なし）**で、同一ルームを複数端末から操作
- GM（司会）は **Start を押した参加者**（司会は死亡しても操作可能）
- 昼は投票 → 処刑、**同数トップは決選投票**を繰り返す
- 夜は役職行動 → 司会が夜明け処理 → 朝結果表示
- **役職公開は司会がトグルで共有**（結果画面）
- スモークテスト `scripts/smoke_flow.py` で一括確認可能

---

# 🧩 使用技術

| 分類 | 技術 |
|------|-------|
| 言語 | Python 3.13 |
| Web Framework | FastAPI |
| データベース | SQLite |
| ORM | SQLAlchemy |
| モデル / Validation | Pydantic v2 |
| テスト | pytest |
| その他 | Uvicorn, HTTPX, UUID |

---

# 🔧 起動方法（ローカル）

```bash
python -m venv .venv
source .venv/bin/activate

# 必要なパッケージをインストール
pip install fastapi uvicorn sqlalchemy pydantic httpx pytest

uvicorn app.main:app --reload
```

---

# 📱 スマホからアクセスする場合

PC をサーバとして使う場合は `--host 0.0.0.0` で起動します。

```bash
uvicorn app.main:app --reload --host 0.0.0.0
```

Mac のローカルIP確認：
```bash
ipconfig getifaddr en0
```

スマホからは `http://<PCのIP>:8000` にアクセスします。

---

# 🗂 画面一覧（実装）

| 画面 | ファイル名 | 説明 |
|------|------------|------|
| ルーム作成（参加者） | `frontend/room_create.html` | Room作成・参加URL共有・GM選択・Start |
| ルーム参加 | `frontend/room_join.html` | 名前登録（roster） |
| 役職確認 | `frontend/role_confirm.html` | 自分の役職確認 → 各フェーズへ遷移 |
| 昼フェーズ | `frontend/day.html` | 投票・集計・処刑確定 |
| 朝フェーズ | `frontend/morning.html` | 夜明け結果の表示 |
| 夜（人狼） | `frontend/night_wolf_attack.html` | 襲撃投票 |
| 夜（占い師） | `frontend/seer_night.html` | 占い |
| 夜（騎士） | `frontend/knight_night.html` | 護衛 |
| 夜（待機） | `frontend/night_wait.html` | 村人/狂人などの待機 |
| 結果 | `frontend/result.html` | 勝敗表示・役職公開 |
| 観戦 | `frontend/spectator.html` | 死亡者/観戦者画面 |

補助・デバッグ：
| 画面 | ファイル名 | 説明 |
|------|------------|------|
| ホスト統合画面 | `frontend/room_host.html` | デバッグ初期化・URL配布 |
| 旧ロビー | `frontend/lobby.html` | 旧フロー（参考） |

---

# 🧠 ゲーム仕様（概要）

## 役職構成（固定）
- 6人：狼2 / 占1 / 騎1 / 狂1 / 村1
- 7人以上：狼2 / 占1 / 騎1 / 狂1 / 霊1 / 村1 + 追加分は村人

## 昼フェーズ
- 生存者全員が投票
- 最多得票者を処刑
- 同数トップの場合は**決選投票**（同数トップのみ対象）
- 司会のみ処刑確定を実行

## 夜フェーズ
- **人狼**：襲撃投票（同数はランダム）
- **占い師**：占い
- **騎士**：護衛
- **村人/狂人**：待機
- 司会が夜明け処理を実行

---

# 📚 API（主要）

※ 詳細は `app/api/v1` を参照。

## Rooms
- `POST /api/rooms`
- `GET /api/rooms/{room_id}`
- `GET /api/rooms/{room_id}/roster`
- `POST /api/rooms/{room_id}/roster`
- `POST /api/rooms/{room_id}/members/bulk_from_roster`

## Games
- `POST /api/games`
- `POST /api/games/{game_id}/start`（`requester_member_id` を指定）
- `GET /api/games/{game_id}/members`
- `GET /api/games/{game_id}/me?player_id=...`

## Day
- `POST /api/games/{game_id}/day_vote`
- `GET /api/games/{game_id}/day_vote_status`
- `POST /api/games/{game_id}/resolve_day_simple`
- `GET /api/games/{game_id}/day_tally`

## Night
- `POST /api/games/{game_id}/wolves/vote`
- `POST /api/games/{game_id}/seer/{seer_member_id}/inspect`
- `POST /api/games/{game_id}/knight/{knight_member_id}/guard`
- `GET /api/games/{game_id}/night_actions_status`
- `POST /api/games/{game_id}/resolve_night_simple`
- `GET /api/games/{game_id}/night_result`

## Result
- `GET /api/games/{game_id}/judge`
- `GET /api/games/{game_id}/reveal_roles`
- `POST /api/games/{game_id}/reveal_roles`

## Debug
- `POST /api/debug/reset_and_seed`
- `POST /api/debug/set_game_members`

---

# ✅ スモークテスト

```bash
python3 scripts/smoke_flow.py
```

7〜15人のケースを含めて通し確認できます。

    S --> T[夜の結果表示]

    T --> U{勝敗が決まった？}
    U -->|決着| R
    U -->|続行| H
```

# 📈 今後の UI 拡張予定

- UI の本実装（HTML → JS → React などへの発展）
- WebSocket を用いたリアルタイム同期（昼夜切替・結果配信）
- 公開ログ画面の実装（誰がいつ何をしたか一覧表示）
- 観戦モードの追加（プレイヤー以外が状況を確認）
- 役職説明ページの追加（初めてのプレイヤー向け）
- スマホ向け UI の最適化（スワイプ操作・タップ領域拡大）
- タイマーのサーバー同期化（クライアント側の時間ズレ防止）
- 騎士の「連続護衛禁止ルール」の追加（オプション化）
- 結果画面の演出強化（アニメーション / ログの自動再生）
- 複数ルーム同時運用の UI 整備（管理画面アップデート）


