from __future__ import annotations

from context import MemoryCreate, MemoryStore


def test_store_creates_and_searches_memory(tmp_path):
    store = MemoryStore(tmp_path / "memories.sqlite3")
    created = store.create_memory(
        MemoryCreate(
            type="preference",
            content="The user prefers verified local commands and concrete URLs.",
            cadence="weekly",
        )
    )

    results = store.search("verified commands", limit=1)

    assert results
    assert results[0].id == created.id
    assert results[0].rank is not None
