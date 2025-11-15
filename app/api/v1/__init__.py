# app/api/v1/__init__.py

from fastapi import APIRouter
from . import profiles, rooms, games

api_router = APIRouter()
api_router.include_router(profiles.router)
api_router.include_router(rooms.router)
api_router.include_router(games.router)

