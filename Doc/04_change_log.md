# 04 変更履歴（Before / After）

本書は、直近の機能追加・仕様変更をポートフォリオ提出向けに整理したものです。  
対象期間は「参加導線改善」から「ゲーム間運用改善」まで。

## 1. 変更サマリ

- 参加導線を URL共有中心から **QR + 待機自動遷移** へ改善
- 参加者の操作を簡素化（登録後は待機のみ）
- GM運用を改善（同一メンバで次ゲーム再開）
- 運用管理機能を追加（ゲーム間メンバ編集、Room削除）
- 回帰テストを追加・整備し、全体テストをグリーン化

## 2. Before / After（機能別）

## 2.1 参加導線

- Before:
  - 参加者にURLを都度共有
  - Start後も個別 `role_confirm` URL配布の負担が大きい
- After:
  - `room_create` で参加URLをQR表示
  - 参加者は `room_join` で登録後待機
  - GMがStartすると参加者は `role_confirm` へ自動遷移

## 2.2 次ゲーム再開

- Before:
  - 次ゲーム開始時の再開導線が弱く、運用が煩雑
- After:
  - GMが `同じメンバで次ゲーム作成` を実行可能
  - `room_join` 側は `current_game_id` 更新を検出して自動追従

## 2.3 メンバ管理（ゲーム間）

- Before:
  - 同一Roomでのゲーム間メンバ調整ができない
- After:
  - `POST /api/rooms/{room_id}/members` で追加
  - `DELETE /api/rooms/{room_id}/members/{member_id}` で削除
  - 進行中ゲーム中は編集禁止（400）

## 2.4 Room管理

- Before:
  - Room削除機能なし
- After:
  - `DELETE /api/rooms/{room_id}` を追加
  - 関連データ（games, game_members, votes, night actions）も削除

## 2.5 GM表示

- Before:
  - GM監視画面に役職露出の懸念
- After:
  - 監視表示は参加者情報中心に調整
  - 役職を表示しない運用へ変更

## 3. 主要コード変更

- フロント:
  - `frontend/room_create.html`
    - QR表示
    - 次ゲーム作成ボタン
    - メンバ追加/削除UI
    - Room削除UI
  - `frontend/room_join.html`
    - 自動遷移ロジック強化
    - `current_game_id` 更新追従
    - 終了ゲーム待機制御
- バックエンド:
  - `app/api/v1/rooms.py`
    - members追加/削除API
    - Room削除API
    - 進行中ゲーム中のメンバ編集ガード
  - `app/schemas/room.py`
    - `RoomMemberCreateRequest` 追加

## 4. テスト変更

- 追加:
  - `tests/test_recent_room_lifecycle.py`
    - 終了後メンバ編集可
    - 進行中メンバ編集不可
    - 同一メンバ次ゲーム作成
    - Room削除時の関連データ削除
- 既存安定化:
  - `tests/test_day_phase.py`
    - 役職ランダム時の投票対象選定を安定化

## 5. 検証結果

- 全体テスト: `68 passed`
- 実施コマンド:
  - `source .venv313/bin/activate`
  - `pytest -q`

## 6. 利用者価値（改善効果）

- 参加者:
  - 登録後は待機のみでよく、操作負担が大幅減
- GM:
  - URL配布負担の削減
  - 同一メンバでの連戦が容易
  - ゲーム間の参加者調整が即時可能
  - 不要Roomを安全にクリーンアップ可能
