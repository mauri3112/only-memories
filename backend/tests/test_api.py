from fastapi.testclient import TestClient

from only_memories.api import app, get_store
from only_memories.schemas import MemoryCreate
from only_memories.store import MemoryStore


def test_health_reports_configured_database_path(tmp_path):
    store = MemoryStore(tmp_path / "configured.sqlite3")
    app.dependency_overrides[get_store] = lambda: store

    try:
        response = TestClient(app).get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database_path": str(store.db_path),
    }


def test_reinforce_missing_memory_returns_404(tmp_path):
    store = MemoryStore(tmp_path / "configured.sqlite3")
    existing = store.create_memory(MemoryCreate(content="An existing memory."))
    app.dependency_overrides[get_store] = lambda: store

    try:
        response = TestClient(app).post(
            "/connections/reinforce",
            json={"source_id": existing.id, "target_id": "missing"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Memory not found"}


def test_forgetting_axiom_returns_conflict(tmp_path):
    store = MemoryStore(tmp_path / "configured.sqlite3")
    axiom = store.create_memory(
        MemoryCreate(type="axiom", axiom_key="identity", content="The user is Mauricio.")
    )
    app.dependency_overrides[get_store] = lambda: store

    try:
        response = TestClient(app).post(
            f"/memories/{axiom.id}/forget",
            json={"reason": "should be impossible"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json() == {"detail": "Axioms cannot be forgotten"}
