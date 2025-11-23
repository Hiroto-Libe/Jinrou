# 🐺 Jinrou Web Game Backend (FastAPI)

スマホ・PCからアクセスし、**同一Wi-Fi上で最大20人がリアルタイムで遊べる人狼ゲーム**のバックエンドAPIです。  
FastAPI + SQLite により、夜の襲撃 → 昼の処刑 → 勝敗判定までの一連の進行が実装されています。

---

# 🚀 主要機能（MVP完成版）

## 🎯 ゲーム基本サイクル

- プロフィール登録  
- ルーム作成  
- 出席簿（RoomRoster）  
- 当日メンバー選択（RoomMember）  
- ゲーム作成（Game）  
- 役職自動配布（GameMember）  
- **ゲームは初日朝からスタート（初夜なし）**
- **初日に占い師へランダム村人1名の“白通知”を自動付与**

---

# 🌅 初日朝フェーズ（ゲーム開始時）

## ✔ 初日＝朝スタート
- ゲームは **DAY_DISCUSSION（朝）** から開始します。  
- 初夜は存在しません。

## ✔ 占い師への初日白通知（自動）
- 役職配布後、占い師へ  
  **「人狼ではない村人1名」をランダムで通知**
- 例：  
  「初日に確認した *はなこ* は **人狼ではありません**」

---

# 🌞 朝フェーズ（議論 → 推理発表）

## 🕒 ① 議論フェーズ（時間は人数で変動）

| 生存人数 | 議論時間 |
|---------|----------|
| 5人以上 | **5分** |
| 4人     | **4分** |
| 3人     | **3分** |
| 2人以下 | 決着間近のため議論スキップ想定 |

- ゲーム序盤は5分  
- 終盤はテンポよく進めるため短縮  
- 将来的に UI カウントダウン実装予定  

## 🗣 ② 推理発表（1人ずつ）
- 「誰が人狼か」
- 「その理由」
- 一人ずつ順番に発表する  
- その後、昼投票へ移行

---

# 🌙 夜フェーズ（NIGHT）

## ✔ 人狼襲撃投票

- 各狼がターゲットへ投票  
- priority_level（1〜3）でポイント加算  
- ポイント最大ターゲットを襲撃  
- 同点ならランダム  

### 投票API例
```json
{
  "wolf_member_id": "WOLF_GAME_MEMBER_ID",
  "target_member_id": "TARGET_GAME_MEMBER_ID",
  "priority_level": 1
}
```

---

## ✔ 夜明け処理（resolve_night_simple）

```text
POST /api/games/{game_id}/resolve_night_simple
```

### 処理内容
- victim.alive = false  
- 状態を DAY_DISCUSSION に移行  
- **自動勝敗判定あり**

---

# 🌞 昼フェーズ（DAY_DISCUSSION）

## ✔ 昼の投票

```json
{
  "voter_member_id": "VOTER_ID",
  "target_member_id": "TARGET_ID"
}
```

- 生存者のみ投票可能  
- 自己投票不可  
- 再投票は上書き  

---

## ✔ 昼決着（resolve_day_simple）

```text
POST /api/games/{game_id}/resolve_day_simple
```

- 最多得票者を追放  
- 同票はランダム  
- NIGHTへ進行  
- **勝敗判定あり**

---

# 🏆 勝敗判定

## ✔ 判定ロジック

- 生存WOLF = 0 → **VILLAGE_WIN**  
- 生存WOLF ≥ 生存VILLAGE → **WOLF_WIN**  
- その他 → **ONGOING**

### 手動判定 API
```text
GET /api/games/{game_id}/judge
```

---

# 🗂 ER図

実体ファイル：  
`Doc/Jinrou_ER図.png`

---

# 🧪 動作確認手順（フル版）

以下は **初日朝スタート → 夜 → 昼 → 村勝利** の完全シナリオです。

---

# 1. プロフィール作成（6名以上）
```json
{
  "display_name": "たろう",
  "avatar_url": "string",
  "note": "テスト参加者1"
}
```

---

# 2. ルーム作成
```json
{
  "name": "A卓"
}
```

---

# 3. 出席簿登録
```json
{
  "profile_id": "PROFILE_ID"
}
```

---

# 4. 当日メンバー登録
```json
{
  "profile_ids": ["id1","id2","id3","id4","id5","id6"]
}
```

---

# 5. ゲーム作成
```json
{
  "room_id": "ROOM_ID",
  "settings": {
    "show_votes_public": true,
    "day_timer_sec": 300,
    "allow_no_kill": false,
    "wolf_vote_lvl1_point": 3,
    "wolf_vote_lvl2_point": 2,
    "wolf_vote_lvl3_point": 1
  }
}
```

---

# 6. 役職配布（+ 占い師白通知）

```
POST /api/games/{game_id}/role_assign
```

---

# 7. 初日朝：議論 → 推理発表
人数に応じた議論時間ルールを適用。

---

# 8. 夜フェーズ：人狼投票
```json
{
  "wolf_member_id": "狼A_ID",
  "target_member_id": "村人_ID",
  "priority_level": 1
}
```

---

# 9. 夜明け処理
```
POST /api/games/{game_id}/resolve_night_simple
```

---

# 10. 昼フェーズ：投票（推理後）
```json
{
  "voter_member_id": "HANAKO_ID",
  "target_member_id": "KOHEI_ID"
}
```

---

# 11. 昼決着 → 村勝利例
```json
{
  "status": "VILLAGE_WIN",
  "victim": { "display_name": "こうへい", "alive": false }
}
```

---

# 12. 最終勝敗確認
```json
{
  "result": "VILLAGE_WIN",
  "wolf_alive": 0,
  "village_alive": 3
}
```

---

# 🔧 開発環境

- Python 3.13  
- FastAPI  
- SQLAlchemy  
- SQLite  
- uvicorn  

### 起動
```bash
uvicorn app.main:app --reload
```

### スマホ接続（同一Wi-Fi）
```
http://<PC-IP>:8000
```

---

# 🎉 Author

- ItoHiroto  
- 目的：FastAPI / Python / ゲームロジック構築ポートフォリオ  

