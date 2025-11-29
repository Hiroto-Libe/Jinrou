# app/main.py
from fastapi import FastAPI

from .db import Base, engine
from .api.v1 import api_router as api_v1_router

# モデルからテーブル作成（開発用）
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Jinrou API",
    version="0.1.0",
)


# v1 API を /api 配下にまとめる
app.include_router(api_v1_router, prefix="/api")


@app.get("/")
def read_root():
    return {"message": "Jinrou API is running"}

