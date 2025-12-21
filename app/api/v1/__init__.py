# app/api/v1/__init__.py

from fastapi import APIRouter

from . import profiles, rooms, games, debug  # 必要なら他のモジュールもここに追加

api_router = APIRouter()

# それぞれの router 側で prefix を持っている前提にする
api_router.include_router(profiles.router)  # profiles.router 内で prefix="/profiles" 等
api_router.include_router(rooms.router)     # rooms.router 内で prefix="/rooms" 等
api_router.include_router(games.router)     # games.router 内で prefix="/games"
api_router.include_router(debug.router)     # debug.router 内で prefix="/debug"
