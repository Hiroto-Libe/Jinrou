# app/schemas/day.py

from pydantic import BaseModel


class DayVoteCreate(BaseModel):
    voter_member_id: str
    target_member_id: str


class DayVoteOut(BaseModel):
    id: str
    game_id: str
    day_no: int
    voter_member_id: str
    target_member_id: str

    class Config:
        from_attributes = True


class DayTallyItem(BaseModel):
    target_member_id: str
    vote_count: int


class DayTallyOut(BaseModel):
    game_id: str
    day_no: int
    items: list[DayTallyItem]


class DayResolveRequest(BaseModel):
    requester_member_id: str


class DayVoteStatusOut(BaseModel):
    game_id: str
    day_no: int
    alive_total: int
    voted_count: int
    all_done: bool
