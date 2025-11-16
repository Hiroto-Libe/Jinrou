# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import Base, engine
from .api.v1 import api_router as api_v1_router
from .models import *  # Profile, Room, RoomRoster, RoomMember, Game, GameMember, WolfVote などを読み込む


def create_app() -> FastAPI:
    app = FastAPI(title="Jinrou Werewolf App")

    # CORS（とりあえず開けておく。あとで絞る）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # モデル定義を読み込んだ上でテーブル作成
    Base.metadata.create_all(bind=engine)

    # REST API v1 を /api 配下にマウント
    app.include_router(api_v1_router, prefix="/api")

    @app.get("/")
    def read_root():
        return {"message": "Jinrou backend is running."}

    return app


app = create_app()
