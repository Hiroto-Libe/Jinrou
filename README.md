# Jinrou（人狼ゲーム API）  
FastAPI × SQLite × SQLAlchemy で構築した **ローカル同室プレイ向けの人狼ゲームバックエンド API** です。  
ゲーム進行（昼・夜）、役職アクション（占い・霊媒・騎士護衛）、勝敗判定までを網羅し、  
**50 以上の自動テストにより全仕様が動作保証**されています。

---

## ✨ 主な特徴

- **完全 API ベース**で構築された人狼ゲームロジック  
- **FastAPI** による自動ドキュメント（Swagger）
- **50+ の pytest テスト**で仕様が保証され、安心して拡張できる
- **SQLite（ファイル or インメモリ）対応**で即動作
- **ローカル同室プレイ前提**のため認証不要、同室内で複数端末から操作可能
- 役職対応：**村人 / 人狼 / 占い師 / 霊媒師 / 狂人 / 騎士**

---

# 🏗️ アーキテクチャ概要
```text 
app/
├── api/
│ ├── v1/
│ │ ├── rooms.py … ルーム作成・参加・メンバー一覧
│ │ ├── games.py … ゲーム開始・状態取得
│ │ ├── day.py … 昼フェーズの投票・処刑
│ │ ├── night.py … 夜フェーズの行動（狼・騎士）
│ │ ├── seer.py … 占い師（夜の占い）
│ │ ├── medium.py … 霊媒師（昼の処刑後判定）
│ │ └── profile.py … プレイヤープロフィール
│
├── models/ … SQLAlchemy モデル
├── schemas/ … Pydantic スキーマ
├── core/logic/ … resolve_day / resolve_night などゲーム進行ロジック
└── main.py … FastAPI エントリポイント
```

---

# 🎮 ゲームの進行フロー

## 1. ルーム作成 → メンバー参加
POST /rooms
POST /rooms/{room_id}/join
GET /rooms/{room_id}/members


## 2. ゲーム開始（役職配布 & 初期ステータス）
POST /games/{room_id}/start


開始直後のステータスは `NIGHT`。

## 3. 夜フェーズ（役職アクション）

- 人狼 → 襲撃投票 (`WOLF_VOTE`)
- 騎士 → 護衛 (`KNIGHT_GUARD`)
- 占い師 → 占い (`SEER_INSPECT`)

全て完了後：

resolve_night_simple()

ここで **死亡判定 / 騎士の護衛処理 / 勝敗判定** を行う。

## 4. 昼フェーズ（議論→投票→処刑）
POST /day/vote
resolve_day_simple()


- 最多票のプレイヤーを処刑  
- 処刑者を `last_executed_member_id` に記録  
- **勝敗判定**

## 5. 終了（FINISHED）

- `VILLAGE_WIN`
- `WOLF_WIN`

結果は `/games/{game_id}` で取得可能。

---

# 🔍 役職仕様

| 役職 | 行動 | 詳細 |
|-----|------|-------|
| 村人 | なし | 投票のみ |
| 人狼 | 夜に1票攻撃 | priority / points により最多得票者を襲撃 |
| 狂人 | 村側に偽装 / 人狼陣営勝利条件にカウント | 占い & 霊媒では常に白 |
| 占い師 | 毎晩 1 人占う | 狼かどうか（狂人は白） |
| 霊媒師 | 昼に処刑された者を判定 | 狼かどうか（狂人は白） |
| 騎士 | 毎晩 1 人護衛 | 連続護衛不可 / 同夜二重護衛不可 / 自己護衛不可（デフォルト） |

---

# 🧠 コアロジック概要

## resolve_night_simple

- 狼の最多得票を集計し襲撃対象を決定
- 騎士の護衛が一致していれば **襲撃無効**
- 不一致の場合 victim.alive = False
- 直後に **勝敗判定（judge_game_result）**
- 結果を以下形式で返す：

```json
{
  "victim": { "id": "xxxx", "role": "VILLAGER" },
  "guarded_success": false,
  "status": {"DAY_DISCUSSION", "WOLF_WIN", "VILLAGE_WIN"}
}
```

## 🌓 resolve_day_simple（昼フェーズ処理）

昼フェーズの投票結果をもとに **処刑対象を決定し、勝敗判定を行うコア処理**です。

### 🔁 処理フロー

## resolve_day_simple

1. 現在のゲーム状態が `DAY_DISCUSSION` であることを確認  
2. 対象日の投票（`DayVote`）を全取得  
3. 最多票のプレイヤーを選出（同票の場合はランダムに 1 名）  
4. 選出されたプレイヤーの生存フラグ（`alive`）を `False` に更新  
5. 処刑されたプレイヤーの ID を `last_executed_member_id` に記録  
6. **勝敗判定（`judge_game_result`）** を実行  
7. 判定結果に応じて状態を更新  
   - 勝敗未決（`ONGOING`）の場合: `status = "NIGHT"` に遷移し、`curr_day` / `curr_night` をインクリメント  
   - 勝敗確定の場合:  
     - `status = "FINISHED"`  
     - `result` に `"VILLAGE_WIN"` / `"WOLF_WIN"` を保存  

戻り値の例:

```json
{
  "game_id": "xxxx",
  "day_no": 1,
  "status": {"NIGHT", "FINISHED",}
  "victim": {
    "id": "member-uuid",
    "display_name": "太郎",
    "role_type": "VILLAGER",
    "team": "VILLAGE",
    "alive": false
  },
  "tally": {
    "target_member_id": "member-uuid",
    "vote_count": 3
  }
}
```

---

## 🧠 judge_game_result（勝敗判定）

ゲームの勝敗を判定する最重要ロジック。

### 判定基準

| 状態 | 条件 |
|------|------|
| **VILLAGE_WIN** | 全ての狼（Werewolf）が死んでいる |
| **WOLF_WIN** | 生存狼陣営数（狼 + 狂人） >= 生存村人数 |
| **ONGOING** | 上記どちらでもない |

### 補足

- 狂人（MADMAN）は「占い・霊媒では白」「勝敗条件では狼側にカウント」として計算される  
- 処刑直後 / 襲撃直後のどちらでも使用される

---

## 💬 役職アクションの仕様詳細

### 占い師（Seer）

- 毎晩 1 名を占う  
- 結果は以下のとおり：  
  - **狼 → true（狼です）**  
  - **村人 / 霊媒師 / 騎士 / 占い師 / 狂人 → false（白）**

### 霊媒師（Medium）

- 昼の処刑後、そのプレイヤーが  
  - 狼なら **true（黒）**  
  - それ以外なら **false（白）**

### 騎士（Knight）

- 毎晩 1 名を護衛  
- 仕様ルール：  
  - 同一夜に二重護衛は不可  
  - **連続同一ターゲット護衛は不可**  
  - 狼襲撃対象と一致した場合 → **襲撃無効**

---

## ⚖ フェーズ遷移（State Machine）
      ┌──────────────┐
      │   GAME_START  │
      └───────┬────────┘
              ▼
          NIGHT (1)
              │ resolve_night
              ▼
    DAY_DISCUSSION (1)
              │ resolve_day
              ▼
          NIGHT (2)
              │
            ...繰り返し...
              │
              ▼
         FINISHED


---

## 📚 API エンドポイント一覧（要約）

| フェーズ | メソッド / パス | 説明 |
|----------|------------------|------|
| ルーム | `POST /rooms` | 作成 |
| | `POST /rooms/{id}/join` | 参加 |
| | `GET /rooms/{id}/members` | メンバー一覧 |
| ゲーム開始 | `POST /games/{room_id}/start` | 役職配布 |
| 昼 | `POST /games/{id}/day/vote` | 投票 |
| | `POST /games/{id}/resolve_day_simple` | 処刑処理 |
| 夜 | `POST /games/{id}/wolf/vote` | 襲撃投票 |
| | `POST /games/{id}/knight/guard` | 騎士護衛 |
| | `POST /games/{id}/seer/inspect` | 占い |
| | `POST /games/{id}/medium/inspect` | 霊媒 |
| | `POST /games/{id}/resolve_night_simple` | 襲撃処理 |

---

## 🧪 テストカバレッジ（56 Tests）

| 分類 | 内容 |
|------|------|
| ルーム管理 | 作成 / 参加 / メンバー一覧 / 参加重複 |
| ゲーム開始 | 役職配布 / エラー処理 |
| 役職ロジック | 狼 / 騎士 / 占い師 / 霊媒師 / 狂人の全仕様 |
| 昼の処刑 | 投票集計 / 同票ランダム / 不正フェーズの拒否 |
| 夜の襲撃 | 襲撃成功・護衛成功・勝敗反映 |
| 勝敗判定 | 村勝利 / 狼勝利 / 継続条件 |
| プロフィール | 作成 / 削除 / 取得 |

---

## 🛠️ 開発環境

- Python 3.13  
- FastAPI  
- SQLAlchemy  
- Pydantic v2  
- SQLite  
- pytest  

---

## 🔮 今後のロードマップ

- UI（スマホ操作画面）
- WebSocket 化によるリアルタイム進行
- 部屋ごとの履歴保存
- 拡張役職（共有者 / 狩人 / 妖狐 etc.）
- クライアント側 SDK 生成（TypeScript）

---

## 📄 ライセンス

MIT

---

必要であれば、  
- **PDF 版 README の生成**  
- **図入りの高クオリティ仕様書**  
- **クリーンアーキテクチャ化の提案**  
なども作成できます。

続きを作成しますか？```

