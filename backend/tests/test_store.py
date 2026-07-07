from __future__ import annotations

from context import MemoryCreate, MemoryStore, SearchScope, SourceLinkCreate


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


def test_axiom_versions_keep_history_but_general_search_returns_current(tmp_path):
    store = MemoryStore(tmp_path / "memories.sqlite3")
    old_name = store.create_memory(
        MemoryCreate(
            type="axiom",
            axiom_key="user-name",
            content="The user's name is Mauricio Oldname.",
            source_links=[
                SourceLinkCreate(
                    label="Contacts card",
                    kind="mac-contacts",
                    uri="x-apple-contacts://person/user-name",
                )
            ],
        )
    )
    current_name = store.create_memory(
        MemoryCreate(
            type="axiom",
            axiom_key="user-name",
            content="The user's name is Mauricio Newname.",
        )
    )

    general_results = store.search("user name", scope=SearchScope.general, limit=10)
    remembering_results = store.search("user name", scope=SearchScope.remembering, limit=10)
    current, versions = store.version_history_for_axiom("user-name")

    assert current.id == current_name.id
    assert current.version == 2
    assert current.supersedes_id == old_name.id
    assert old_name.id not in {memory.id for memory in general_results}
    assert {old_name.id, current_name.id}.issubset({memory.id for memory in remembering_results})
    assert [memory.version for memory in versions] == [2, 1]
    assert store.get_memory(old_name.id).source_links[0].kind == "mac-contacts"
