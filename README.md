# Jinrou - Web人狼ゲーム（FastAPI + HTML/JS）

本リポジトリは、FastAPI をバックエンドにした Web 人狼ゲームです。  
現在は **ルーム作成 -> 参加登録 -> GM開始 -> 各参加者が自動遷移で役職画面へ** の流れで動作します。

## 現在の主要仕様

- ルーム作成画面: `frontend/room_create.html`
- 参加画面: `frontend/room_join.html`
- 役職確認画面: `frontend/role_confirm.html`
- 参加者登録は `room_join` で待機し、GM が Start すると `role_confirm` へ自動遷移
- `room_create` では参加URLの QR 表示に対応
- GM 側画面では役職を表示しない運用（参加者一覧のみ表示）

## 起動方法（ローカル）

### 1) 仮想環境を有効化

```bash
source .venv313/bin/activate
```

### 2) API サーバ起動

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## アクセス先

- GM（ホスト）: `http://<PCのIP>:8000/frontend/room_create.html`
- 参加者: GM が表示した参加URL（またはQR）から `room_join` へ

## 推奨運用フロー

1. GM が `room_create` で Room を作成
2. 参加者は QR を読み取り `room_join` で名前登録
3. GM が `roster更新` -> `rosterを確定` -> `Game作成` -> `Start`
4. 参加者端末は待機画面から自動で `role_confirm` に遷移

## テスト

自動テストは `pytest` で実行します。

```bash
source .venv313/bin/activate
pytest -q
```

現時点の確認結果: **61 passed**

## ディレクトリ概要

- `app/`: FastAPI アプリ本体（API, モデル, スキーマ）
- `frontend/`: 各画面の HTML/JS
- `tests/`: pytest による自動テスト
- `scripts/`: 補助スクリプト（スモークテスト等）
