from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .db import Base, engine, ensure_room_members_schema
from .api.v1 import api_router as api_v1_router

# モデルからテーブル作成（開発用）
Base.metadata.create_all(bind=engine)
ensure_room_members_schema()

app = FastAPI(
    title="Jinrou API",
    version="0.1.0",
)

# ローカル開発用のCORS許可（静的サーバからのアクセス用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ▼ 追加：frontend ディレクトリを静的ファイルとして公開
app.mount(
    "/frontend",
    StaticFiles(directory="frontend", html=True),
    name="frontend",
)

# ▼ 既存：API ルーター
app.include_router(api_v1_router, prefix="/api")


@app.get("/")
def read_root():
    return {"message": "Jinrou API is running"}
