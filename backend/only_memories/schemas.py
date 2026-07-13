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


class MemoryPlane(StrEnum):
    knowledge = "knowledge"
    activity = "activity"


class ProvenanceClass(StrEnum):
    user_assertion = "user_assertion"
    primary_source = "primary_source"
    imported_observation = "imported_observation"
    agent_inference = "agent_inference"
    agent_recap = "agent_recap"
    system_event = "system_event"


class VerificationStatus(StrEnum):
    unverified = "unverified"
    corroborated = "corroborated"
    verified = "verified"
    disputed = "disputed"
    retracted = "retracted"


class SearchIntent(StrEnum):
    answer = "answer"
    evidence = "evidence"
    action = "action"
    maintenance = "maintenance"
    audit = "audit"


class MemoryRelation(StrEnum):
    related = "related"
    updates = "updates"
    extends = "extends"
    derives = "derives"
    supports = "supports"


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
    relation: MemoryRelation = MemoryRelation.related


class MemoryCreate(BaseModel):
    type: MemoryType = MemoryType.note
    content: str = Field(min_length=1)
    happened_at: datetime | None = None
    source: str = "manual"
    space_id: str = Field(default="default", min_length=1)
    plane: MemoryPlane = MemoryPlane.knowledge
    provenance_class: ProvenanceClass = ProvenanceClass.imported_observation
    verification_status: VerificationStatus = VerificationStatus.unverified
    producer: str | None = None
    origin_run_id: str | None = None
    derivation_depth: int = Field(default=0, ge=0)
    external_key: str | None = None
    source_links: list[SourceLinkCreate] = Field(default_factory=list)
    cadence: Cadence = Cadence.none
    expires_at: datetime | None = None
    base_importance: float = Field(default=0.5, ge=0, le=1)
    axiom_key: str | None = None
    supersedes_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    connections: list[ConnectionCreate] = Field(default_factory=list)


class MemoryUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1)
    cadence: Cadence | None = None
    expires_at: datetime | None = None
    base_importance: float | None = Field(default=None, ge=0, le=1)
    is_forgotten: bool | None = None
    forget_reason: str | None = None
    source_links: list[SourceLinkCreate] | None = None
    metadata: dict[str, Any] | None = None


class ForgetMemoryRequest(BaseModel):
    reason: str | None = None


class Memory(BaseModel):
    id: str
    type: MemoryType
    content: str
    happened_at: datetime
    created_at: datetime
    updated_at: datetime
    source: str
    space_id: str = "default"
    plane: MemoryPlane = MemoryPlane.knowledge
    provenance_class: ProvenanceClass = ProvenanceClass.imported_observation
    verification_status: VerificationStatus = VerificationStatus.unverified
    producer: str | None = None
    origin_run_id: str | None = None
    derivation_depth: int = 0
    external_key: str | None = None
    source_links: list[SourceLink] = Field(default_factory=list)
    cadence: Cadence
    expires_at: datetime | None
    base_importance: float
    access_count: int
    axiom_key: str | None = None
    version: int = 1
    supersedes_id: str | None = None
    is_current: bool = True
    is_forgotten: bool = False
    forgotten_at: datetime | None = None
    forget_reason: str | None = None
    metadata: dict[str, Any]
    rank: float | None = None
    rank_breakdown: dict[str, float] | None = None


class Connection(BaseModel):
    source_id: str
    target_id: str
    weight: float
    relation: MemoryRelation
    reason: str
    created_at: datetime


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)
    type: MemoryType | None = None
    types: list[MemoryType] = Field(default_factory=list)
    exclude_types: list[MemoryType] = Field(default_factory=list)
    intent: SearchIntent = SearchIntent.answer
    space_ids: list[str] = Field(default_factory=list)
    planes: list[MemoryPlane] = Field(default_factory=lambda: [MemoryPlane.knowledge])
    provenance_classes: list[ProvenanceClass] = Field(default_factory=list)
    verification_statuses: list[VerificationStatus] = Field(default_factory=list)
    include_generated: bool = False
    scope: SearchScope = SearchScope.general
    include_forgotten: bool = False
    include_expired: bool = False


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


class RankBreakdown(BaseModel):
    importance: float
    recency: float
    cadence: float
    connectedness: float
    total: float


class GraphNode(BaseModel):
    memory: Memory


class GraphResponse(BaseModel):
    origin: Memory
    nodes: list[Memory]
    edges: list[Connection]


class MaintenanceProposalType(StrEnum):
    retire_expired = "retire_expired"
    collapse_duplicate = "collapse_duplicate"
    add_connection = "add_connection"


class MaintenanceProposalStatus(StrEnum):
    pending = "pending"
    applied = "applied"
    dismissed = "dismissed"


class MaintenanceProposal(BaseModel):
    id: str
    run_id: str
    type: MaintenanceProposalType
    status: MaintenanceProposalStatus
    memory_id: str
    target_id: str | None = None
    reason: str
    score: float | None = None
    created_at: datetime
    decided_at: datetime | None = None


class MaintenanceRun(BaseModel):
    id: str
    created_at: datetime
    proposals: list[MaintenanceProposal]


class MaintenanceActionResponse(BaseModel):
    proposal: MaintenanceProposal
    memory: Memory | None = None
