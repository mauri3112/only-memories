from __future__ import annotations

from functools import lru_cache

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .schemas import (
    Connection,
    Memory,
    MemoryCreate,
    MemoryUpdate,
    NavigateResponse,
    ReinforceConnectionRequest,
    SearchRequest,
    SearchResponse,
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
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/memories", response_model=Memory)
def create_memory(payload: MemoryCreate, store: MemoryStore = Depends(get_store)) -> Memory:
    return store.create_memory(payload)


@app.get("/memories", response_model=list[Memory])
def list_memories(
    limit: int = 50,
    type: str | None = None,
    store: MemoryStore = Depends(get_store),
) -> list[Memory]:
    return store.list_memories(limit=limit, memory_type=type)


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


@app.post("/search", response_model=SearchResponse)
def search(payload: SearchRequest, store: MemoryStore = Depends(get_store)) -> SearchResponse:
    return SearchResponse(
        query=payload.query,
        results=store.search(payload.query, limit=payload.limit, memory_type=payload.type),
    )


@app.get("/memories/{memory_id}/connections", response_model=list[Connection])
def connections(memory_id: str, store: MemoryStore = Depends(get_store)) -> list[Connection]:
    return store.connections_for(memory_id)


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


@app.post("/connections/reinforce")
def reinforce_connection(
    payload: ReinforceConnectionRequest,
    store: MemoryStore = Depends(get_store),
) -> dict[str, str]:
    store.reinforce_connection(
        payload.source_id,
        payload.target_id,
        amount=payload.amount,
        reason=payload.reason,
    )
    return {"status": "ok"}


def run() -> None:
    settings = get_settings()
    uvicorn.run("only_memories.api:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    run()
