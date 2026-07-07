from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MemoryType(StrEnum):
    axiom = "axiom"
    preference = "preference"
    project = "project"
    person = "person"
    decision = "decision"
    concept = "concept"
    source = "source"
    task = "task"
    event = "event"
    artifact = "artifact"
    skill = "skill"
    system = "system"
    note = "note"


class Cadence(StrEnum):
    none = "none"
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    seasonal = "seasonal"


class SearchScope(StrEnum):
    general = "general"
    remembering = "remembering"


class SourceLinkCreate(BaseModel):
    label: str = Field(min_length=1)
    kind: str = Field(default="manual", min_length=1)
    uri: str = Field(min_length=1)
    open_hint: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceLink(SourceLinkCreate):
    id: str
    memory_id: str
    created_at: datetime


class ConnectionCreate(BaseModel):
    target_id: str
    weight: float = Field(default=0.5, ge=0, le=1)
    reason: str = "manual"


class MemoryCreate(BaseModel):
    type: MemoryType = MemoryType.note
    content: str = Field(min_length=1)
    happened_at: datetime | None = None
    source: str = "manual"
    source_links: list[SourceLinkCreate] = Field(default_factory=list)
    cadence: Cadence = Cadence.none
    expires_at: datetime | None = None
    base_importance: float = Field(default=0.5, ge=0, le=1)
    axiom_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    connections: list[ConnectionCreate] = Field(default_factory=list)


class MemoryUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1)
    cadence: Cadence | None = None
    expires_at: datetime | None = None
    base_importance: float | None = Field(default=None, ge=0, le=1)
    source_links: list[SourceLinkCreate] | None = None
    metadata: dict[str, Any] | None = None


class Memory(BaseModel):
    id: str
    type: MemoryType
    content: str
    happened_at: datetime
    created_at: datetime
    updated_at: datetime
    source: str
    source_links: list[SourceLink] = Field(default_factory=list)
    cadence: Cadence
    expires_at: datetime | None
    base_importance: float
    access_count: int
    axiom_key: str | None = None
    version: int = 1
    supersedes_id: str | None = None
    is_current: bool = True
    metadata: dict[str, Any]
    rank: float | None = None


class Connection(BaseModel):
    source_id: str
    target_id: str
    weight: float
    reason: str
    created_at: datetime


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)
    type: MemoryType | None = None
    scope: SearchScope = SearchScope.general


class SearchResponse(BaseModel):
    query: str
    results: list[Memory]


class NavigateResponse(BaseModel):
    origin: Memory
    connections: list[Memory]


class VersionHistoryResponse(BaseModel):
    current: Memory
    versions: list[Memory]


class ReinforceConnectionRequest(BaseModel):
    source_id: str
    target_id: str
    amount: float = Field(default=0.1, gt=0, le=1)
    reason: str = "reinforced"
