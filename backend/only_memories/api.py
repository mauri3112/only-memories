from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .schemas import (
    Connection,
    ForgetMemoryRequest,
    GraphResponse,
    MaintenanceActionResponse,
    MaintenanceProposal,
    MaintenanceRun,
    Memory,
    MemoryCreate,
    MemoryUpdate,
    NavigateResponse,
    ReinforceConnectionRequest,
    SearchRequest,
    SearchResponse,
    SourceLink,
    VersionHistoryResponse,
)
from .store import MemoryStore

app = FastAPI(
    title="only-memories",
    description="Local-first memory graph service for LLM agents.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def get_store() -> MemoryStore:
    return MemoryStore(get_settings().db_path)


@app.get("/health")
def health(store: MemoryStore = Depends(get_store)) -> dict[str, str]:
    return {"status": "ok", "database_path": str(store.db_path)}


@app.post("/memories", response_model=Memory)
def create_memory(
    payload: MemoryCreate,
    store: MemoryStore = Depends(get_store),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> Memory:
    try:
        return (
            store.create_memory_idempotent(payload, idempotency_key)
            if idempotency_key
            else store.create_memory(payload)
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail="Superseded memory not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/memories", response_model=list[Memory])
def list_memories(
    limit: int = 50,
    type: str | None = None,
    include_versions: bool = False,
    include_forgotten: bool = False,
    include_expired: bool = False,
    store: MemoryStore = Depends(get_store),
) -> list[Memory]:
    return store.list_memories(
        limit=limit,
        memory_type=type,
        include_versions=include_versions,
        include_forgotten=include_forgotten,
        include_expired=include_expired,
    )


@app.get("/memories/{memory_id}", response_model=Memory)
def get_memory(memory_id: str, store: MemoryStore = Depends(get_store)) -> Memory:
    try:
        store.touch(memory_id)
        return store.get_memory(memory_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Memory not found") from exc


@app.patch("/memories/{memory_id}", response_model=Memory)
def update_memory(
    memory_id: str,
    payload: MemoryUpdate,
    store: MemoryStore = Depends(get_store),
) -> Memory:
    try:
        return store.update_memory(memory_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Memory not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/memories/{memory_id}/forget", response_model=Memory)
def forget_memory(
    memory_id: str,
    payload: ForgetMemoryRequest | None = None,
    store: MemoryStore = Depends(get_store),
) -> Memory:
    try:
        return store.forget_memory(memory_id, reason=payload.reason if payload else None)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Memory not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/memories/{memory_id}/restore", response_model=Memory)
def restore_memory(memory_id: str, store: MemoryStore = Depends(get_store)) -> Memory:
    try:
        return store.restore_memory(memory_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Memory not found") from exc


@app.post("/search", response_model=SearchResponse)
def search(payload: SearchRequest, store: MemoryStore = Depends(get_store)) -> SearchResponse:
    return SearchResponse(
        query=payload.query,
        results=store.search(
            payload.query,
            limit=payload.limit,
            memory_type=payload.type,
            memory_types=[item.value for item in payload.types],
            exclude_types=[item.value for item in payload.exclude_types],
            intent=payload.intent,
            space_ids=payload.space_ids,
            planes=[item.value for item in payload.planes],
            provenance_classes=[item.value for item in payload.provenance_classes],
            verification_statuses=[item.value for item in payload.verification_statuses],
            include_generated=payload.include_generated,
            scope=payload.scope,
            include_forgotten=payload.include_forgotten,
            include_expired=payload.include_expired,
        ),
    )


@app.get("/memories/{memory_id}/connections", response_model=list[Connection])
def connections(memory_id: str, store: MemoryStore = Depends(get_store)) -> list[Connection]:
    return store.connections_for(memory_id)


@app.get("/memories/{memory_id}/sources", response_model=list[SourceLink])
def source_links(memory_id: str, store: MemoryStore = Depends(get_store)) -> list[SourceLink]:
    return store.source_links_for(memory_id)


@app.get("/memories/{memory_id}/versions", response_model=VersionHistoryResponse)
def memory_versions(
    memory_id: str,
    store: MemoryStore = Depends(get_store),
) -> VersionHistoryResponse:
    try:
        current, versions = store.version_history_for_memory(memory_id)
        return VersionHistoryResponse(current=current, versions=versions)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Memory not found") from exc


@app.get("/axioms/{axiom_key}/versions", response_model=VersionHistoryResponse)
def axiom_versions(
    axiom_key: str,
    store: MemoryStore = Depends(get_store),
) -> VersionHistoryResponse:
    try:
        current, versions = store.version_history_for_axiom(axiom_key)
        return VersionHistoryResponse(current=current, versions=versions)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Axiom not found") from exc


@app.get("/memories/{memory_id}/navigate", response_model=NavigateResponse)
def navigate(
    memory_id: str,
    limit: int = 10,
    store: MemoryStore = Depends(get_store),
) -> NavigateResponse:
    try:
        origin, related = store.navigate(memory_id, limit=limit)
        return NavigateResponse(origin=origin, connections=related)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Memory not found") from exc


@app.get("/memories/{memory_id}/graph", response_model=GraphResponse)
def graph(memory_id: str, limit: int = 10, store: MemoryStore = Depends(get_store)) -> GraphResponse:
    try:
        origin, nodes, edges = store.graph_for(memory_id, limit=limit)
        return GraphResponse(origin=origin, nodes=nodes, edges=edges)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Memory not found") from exc


@app.post("/maintenance/preview", response_model=MaintenanceRun)
def preview_maintenance(store: MemoryStore = Depends(get_store)) -> MaintenanceRun:
    run_id, proposals = store.preview_maintenance()
    return MaintenanceRun(
        id=run_id,
        created_at=min(
            (proposal["created_at"] for proposal in proposals),
            default=datetime.now(UTC),
        ),
        proposals=[MaintenanceProposal.model_validate(proposal) for proposal in proposals],
    )


@app.get("/maintenance/proposals", response_model=list[MaintenanceProposal])
def maintenance_proposals(
    run_id: str | None = None, store: MemoryStore = Depends(get_store)
) -> list[MaintenanceProposal]:
    return [MaintenanceProposal.model_validate(item) for item in store.maintenance_proposals(run_id)]


@app.post("/maintenance/proposals/{proposal_id}/apply", response_model=MaintenanceActionResponse)
def apply_maintenance(
    proposal_id: str, store: MemoryStore = Depends(get_store)
) -> MaintenanceActionResponse:
    try:
        proposal, memory = store.decide_maintenance(proposal_id, apply=True)
        return MaintenanceActionResponse(
            proposal=MaintenanceProposal.model_validate(proposal), memory=memory
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Maintenance proposal not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/maintenance/proposals/{proposal_id}/dismiss", response_model=MaintenanceActionResponse)
def dismiss_maintenance(
    proposal_id: str, store: MemoryStore = Depends(get_store)
) -> MaintenanceActionResponse:
    try:
        proposal, memory = store.decide_maintenance(proposal_id, apply=False)
        return MaintenanceActionResponse(
            proposal=MaintenanceProposal.model_validate(proposal), memory=memory
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Maintenance proposal not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/connections/reinforce")
def reinforce_connection(
    payload: ReinforceConnectionRequest,
    store: MemoryStore = Depends(get_store),
) -> dict[str, str]:
    try:
        store.reinforce_connection(
            payload.source_id,
            payload.target_id,
            amount=payload.amount,
            reason=payload.reason,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Memory not found") from exc
    return {"status": "ok"}


def run() -> None:
    settings = get_settings()
    uvicorn.run("only_memories.api:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    run()
