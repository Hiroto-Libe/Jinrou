# 🐺 Jinrou Web Game Backend (FastAPI)

スマホ・PC からアクセスし、  
**同一 Wi-Fi 上で最大 20 人がリアルタイムで遊べる人狼ゲーム** のバックエンド API です。

FastAPI + SQLite を使い、  
夜の人狼投票 → 昼の処刑 → 勝敗判定までの一連のゲーム進行が実現されています。

---

# 🚀 主要機能（MVP 完成版）

## 🎯 ゲームの基本サイクル
- 参加者登録（プロフィール管理）
- 出席メンバーの選択（ルームごと）
- ゲーム作成（Game）
- 役職の自動配布（人数に応じて狼・占い師・騎士などを自動割り当て）

---

## 🌙 夜フェーズ（NIGHT）
### ✔ 人狼の襲撃投票
- 各狼がターゲットを選ぶ
- 優先度（lvl1, lvl2, lvl3）によってポイントが変動
- ポイント合計が最大のプレイヤーが襲撃対象（同点ならランダム）

### ✔ 夜明け処理（resolve_night_simple）
- 襲撃結果を反映（alive=False）
- ゲームステータス → `DAY_DISCUSSION`（昼へ）
- **自動で勝敗判定**
  - 人狼生存 0 → VILLAGE_WIN  
  - 人狼数 >= 村人数 → WOLF_WIN  
  - それ以外 → 継続

---

## 🌞 昼フェーズ（DAY_DISCUSSION）
### ✔ プレイヤー投票（day_vote）
- 生存者のみ投票可能
- 自分へ投票は不可
- 再投票すると前回を上書き

### ✔ 昼決着（resolve_day_simple）
- 最多得票の player を追放（alive=False）
- 同票はランダム
- フェーズを NIGHT に進める
- **自動で勝敗判定**（夜と同じロジック）

---

## 🏆 勝敗判定（自動 & 手動チェック）
### ✔ 自動判定（夜明け・昼決着後に毎回動作）
人狼が 0 → 村勝利（VILLAGE_WIN）
人狼数 >= 村人数 → 狼勝利（WOLF_WIN）

### ✔ 手動 API（現在の状況を確認）
GET /api/games/{game_id}/judge

---

## 👥 メンバー関連機能
- プロフィール登録（ニックネーム・アバターURL）
- ルームごとの常連メンバー管理
- ゲーム当日の参加メンバー選択（RDB永続化）

---

# 🗂 ER図
※ PNG は `/Doc/Jinrou_ER図.png` にあります。
（GitHub の場合は画像を README と同階層か Doc フォルダに置けば自動プレビューされます）

ユーザー（Profile）
↓ ルーム参加（RoomRoster）
ルーム（Room）
↓ 当日メンバー（RoomMember）
ゲーム（Game）
├─ ゲーム参加者（GameMember）
├─ 夜の投票（WolfVote）
└─ 昼の投票（DayVote）

---

# 🧪 動作確認手順（完全版）

以下の手順に従うと、  
**実際に「村勝利」までの一連の進行を確認できます。**

---

## ① プロフィールを複数作成（6人以上）
POST /api/profiles

例：

```json
{
  "display_name": "たろう",
  "avatar_url": "string",
  "note": "テスト参加者1"
}
6人分登録 → /api/profiles で確認

## ② ルーム作成
POST /api/rooms

POST /api/rooms

例：
{
  "name": "A卓"
}

## ③ ルームにメンバー登録（出席簿追加）
POST /api/rooms/{room_id}/roster

プロフィールIDを指定：
{
  "profile_id": "XXXX-profile-id"
}
6人分繰り返す。

## ④ 当日のメンバー選択（RoomMember 化）
POST /api/rooms/{room_id}/members/bulk_from_roster

例：
{
  "profile_ids": [
    "id1","id2","id3","id4","id5","id6"
  ]
}

## ⑤ ゲーム作成
POST /api/games

例：
{
  "room_id": "A卓のroom_id",
  "settings": {
    "show_votes_public": true,
    "day_timer_sec": 300,
    "knight_self_guard": false,
    "knight_consecutive_guard": false,
    "allow_no_kill": false,
    "wolf_vote_lvl1_point": 3,
    "wolf_vote_lvl2_point": 2,
    "wolf_vote_lvl3_point": 1
  }
}

## ⑥ 役職配布
POST /api/games/{game_id}/role_assign

返信JSONに各 GameMember の ID が入っているので控える。


## ⑦ 夜フェーズ（NIGHT）
ゲームのステータスが NIGHT であることを確認。
人狼が襲撃投票
POST /api/games/{game_id}/wolves/vote

夜明け処理
POST /api/games/{game_id}/resolve_night_simple

勝敗が決まっていれば status=VILLAGE_WIN or WOLF_WIN

## ⑧ 昼フェーズ（DAY_DISCUSSION）
投票（生存者→ターゲット）
POST /api/games/{game_id}/day_vote

例（はなこ → こうへい）：
{
  "voter_member_id": "98f6b61a-ee20-4d59-b887-51a726bb61f4",
  "target_member_id": "70a5c24e-7f10-48d4-b887-51a726bb61f4"
}
全生存者について繰り返す。

## ⑨ 昼の決着（resolve_day_simple）
POST /api/games/{game_id}/resolve_day_simple

こうへい（最後の狼）を処刑した例：
{
  "status": "VILLAGE_WIN",
  "victim": { "display_name": "こうへい", "alive": false }
}

## 🔟 勝敗最終確認
GET /api/games/{game_id}/judge

---

# 🔧 開発環境
- Python 3.13
- FastAPI
- SQLAlchemy
- SQLite（ローカル実行用）
- uvicorn（ローカルサーバー）

起動：
uvicorn app.main:app --reload

スマホアクセス（同一Wi-Fi）：
http://<PCのIPアドレス>:8000

---

# 📝 今後の発展予定
- 占い師・騎士・霊媒師の夜行動 API
- 狼同士のリアルタイム相談（WebSocket）
- 吊られた瞬間に役職公開などの設定追加
- 超シンプルなスマホWeb UI

---

# 🎉 Author
ItoHiroto
Portfolio purpose: Python / FastAPI / Backend Development
このプロジェクトは 実務レベルのAPI設計・DB設計・ゲームロジック実装 を目的に作成。

---

# 📌 次にやるなら？
- README を GitHub にアップ
- Link をプロフィールに掲載
- 次は「夜の役職行動」 or 「簡易UI」どちらかでフロント着手できます！

必要があれば README に画像埋め込み版や章立て調整などもできますよ。
