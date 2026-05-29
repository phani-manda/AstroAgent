from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlmodel import SQLModel, Field, Column, JSON


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Message(SQLModel, table=False):
    role: str
    content: str
    created_at: datetime = Field(default_factory=_utcnow)


class Conversation(SQLModel, table=True):
    id: str = Field(primary_key=True)
    messages: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    birth: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    chart: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=_utcnow)


class BirthInfo(SQLModel):
    date: str
    time: Optional[str] = None
    place: str


class ChartData(SQLModel):
    planets: Dict[str, float]
    houses: Dict[int, float]
    ascendant: float
    mc: float


class GeocodeResult(SQLModel):
    lat: float
    lng: float
    tz: str


class TransitAspect(SQLModel):
    planet: str
    aspect: str
    natal_planet: str
