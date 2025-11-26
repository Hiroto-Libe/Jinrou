# 🐺 人狼Webアプリ 詳細設計書（更新版）
更新日: 2025-xx-xx

本ドキュメントは Web ベース人狼ゲームのバックエンド実装の詳細設計仕様を示す。

狂人（MADMAN）追加および霊媒師 API 実装に対応。

---

# 1. アーキテクチャ構成

- FastAPI（REST）
- SQLite（SQLAlchemy ORM）
- WebSocket は将来拡張
- Pydantic v2（from_attributes利用）

---

# 2. データモデル詳細（更新版）

## 2.1 Game

| フィールド | 型 | 説明 |
|-----------|----|------|
| id | str | ゲームID |
| room_id | str | 部屋ID |
| status | str | WAITING/NIGHT/DAY_DISCUSSION/... |
| curr_day | int | 昼の日数 |
| curr_night | int | 夜の日数 |
| last_executed_member_id | str | 前日の処刑者ID（霊媒用） |
| seer_first_white_target_id | str | 初日白通知対象 |

---

## 2.2 GameMember

| フィールド | 説明 |
|-----------|------|
| role_type | VILLAGER / WEREWOLF / SEER / MEDIUM / KNIGHT / MADMAN |
| team | VILLAGE or WOLF |
| alive | bool |
| display_name | 表示名 |
| order_no | 並び順 |

team ロジック：

```
WOLF陣営 = WEREWOLF / MADMAN
VILLAGE陣営 = その他
```

---

## 2.3 MediumInspect

| フィールド | 説明 |
|-----------|------|
| id | UUID |
| game_id | ゲームID |
| day_no | 処刑が行われた昼の日 |
| medium_member_id | 霊媒師 |
| target_member_id | 前日の処刑者 |
| is_wolf | bool |

---

# 3. REST API 詳細

## 3.1 役職配布  
`POST /games/{game_id}/role_assign`

人数に応じて自動役職配布。

狂人（MADMAN）を 1 名付与。

### 人数別構成

| 人数 | 配布例 |
|------|--------|
| 6 | 狼2/占/騎/村/狂 |
| 7 | 狼2/占/騎/村2/狂 |
| 8 | 狼2/占/霊/騎/村2/狂 |
| 9 | 狼2/占/霊/騎/村3/狂 |
| 10 | 狼2/占/霊/騎/村4/狂 |

---

## 3.2 昼決着  
`POST /games/{game_id}/resolve_day_simple`

- 最多票を処刑
- `game.last_executed_member_id = victim.id`
- curr_day+1, curr_night+1 へ進行
- 勝敗判定あり

---

## 3.3 霊媒師  
`POST /games/{game_id}/medium/{medium_member_id}/inspect`

### 事前条件

| 条件 | 内容 |
|------|------|
| Night中 | Game.status == NIGHT |
| Medium本人 | medium.role_type == MEDIUM |
| 生存 | medium.alive == True |
| 前日の処刑あり | last_executed_member_id が存在 |
| 1日1回 | MediumInspect が同じ day_no に存在しない |

### 出力

- day_no = curr_day - 1
- is_wolf = (target.team == "WOLF")

---

# 4. ビジネスロジック詳細

## 4.1 昼 → 夜

- 投票結果で victim を決定
- victim.alive=False
- last_executed_member_id 更新
- 勝敗判定
- NEXT NIGHT

---

## 4.2 夜 → 朝

- 狼投票集計（priority制）
- 騎士護衛チェック
- 襲撃成功なら victim.alive=False
- 勝敗判定
- NEXT DAY_DISCUSSION

---

# 5. 勝敗判定

狼陣営 = WEREWOLF + MADMAN  
村陣営 = team == VILLAGE

```
狼0 → 村勝利
狼 >= 村 → 狼勝利
```

---

# 6. テスト設計

## 6.1 Unit Test

- MediumInspect（霊媒師API）
- decide_roles（狂人追加が正しいか）
- resolve_day_simple
- resolve_night_simple

## 6.2 E2E Test（予定）

- 昼→夜→霊媒→昼のフローを FastAPI TestClient で実装

---

# 7. 今後の拡張

- 役職追加（FOX/共有者）
- 自動フェーズ遷移
- WebSocket 通知
- GitHub Actions で自動テスト
- Pydantic v2 ConfigDict 対応

---
