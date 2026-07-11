from __future__ import annotations

from datetime import UTC, datetime, timedelta

from context import (
    ConnectionCreate,
    MemoryCreate,
    MemoryStore,
    SearchScope,
    SourceLinkCreate,
)
from only_memories.schemas import MemoryUpdate


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


def test_superseded_non_axiom_memories_form_update_chain(tmp_path):
    store = MemoryStore(tmp_path / "memories.sqlite3")
    old_role = store.create_memory(
        MemoryCreate(
            type="person",
            content="Alex works at Google as a software engineer.",
        )
    )
    new_role = store.create_memory(
        MemoryCreate(
            type="person",
            content="Alex works at Stripe as a product manager.",
            supersedes_id=old_role.id,
        )
    )

    general_results = store.search("where does Alex work", scope=SearchScope.general, limit=10)
    remembering_results = store.search(
        "where does Alex work",
        scope=SearchScope.remembering,
        limit=10,
    )
    current, versions = store.version_history_for_memory(old_role.id)
    update_edges = store.connections_for(new_role.id)

    assert current.id == new_role.id
    assert new_role.version == 2
    assert store.get_memory(old_role.id).is_current is False
    assert old_role.id not in {memory.id for memory in general_results}
    assert {old_role.id, new_role.id}.issubset({memory.id for memory in remembering_results})
    assert [memory.version for memory in versions] == [2, 1]
    assert any(
        edge.target_id == old_role.id and edge.relation == "updates" for edge in update_edges
    )


def test_connection_relations_are_stored_with_edges(tmp_path):
    store = MemoryStore(tmp_path / "memories.sqlite3")
    base = store.create_memory(MemoryCreate(content="The user is learning graph memory."))
    detail = store.create_memory(
        MemoryCreate(
            content="The user is comparing relation labels.",
            connections=[
                ConnectionCreate(
                    target_id=base.id,
                    weight=0.8,
                    relation="extends",
                    reason="manual test",
                )
            ],
        )
    )

    edges = store.connections_for(detail.id)

    assert any(edge.target_id == base.id and edge.relation == "extends" for edge in edges)


def test_forgotten_and_expired_memories_are_hidden_by_default(tmp_path):
    store = MemoryStore(tmp_path / "memories.sqlite3")
    active = store.create_memory(MemoryCreate(content="The user currently prefers Puma."))
    forgotten = store.create_memory(MemoryCreate(content="The user used to prefer Adidas."))
    expired = store.create_memory(
        MemoryCreate(
            content="The user has an exam tomorrow.",
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
    )

    store.forget_memory(forgotten.id, reason="outdated preference")

    default_results = store.search("user prefers exam", limit=10)
    audit_results = store.search(
        "user prefers exam",
        limit=10,
        include_forgotten=True,
        include_expired=True,
    )

    assert active.id in {memory.id for memory in default_results}
    assert forgotten.id not in {memory.id for memory in default_results}
    assert expired.id not in {memory.id for memory in default_results}
    assert {forgotten.id, expired.id}.issubset({memory.id for memory in audit_results})
    assert store.get_memory(forgotten.id).forget_reason == "outdated preference"


def test_content_edits_create_versions_but_metadata_edits_do_not(tmp_path):
    store = MemoryStore(tmp_path / "memories.sqlite3")
    original = store.create_memory(MemoryCreate(type="decision", content="Use the old layout."))

    metadata_edit = store.update_memory(original.id, MemoryUpdate(base_importance=0.8))
    replacement = store.update_memory(
        original.id,
        MemoryUpdate(content="Use the new operator-console layout."),
    )
    current, versions = store.version_history_for_memory(original.id)

    assert metadata_edit.id == original.id
    assert replacement.id != original.id
    assert replacement.supersedes_id == original.id
    assert current.id == replacement.id
    assert [version.version for version in versions] == [2, 1]


def test_maintenance_preview_requires_decision_and_collapses_duplicate(tmp_path):
    store = MemoryStore(tmp_path / "memories.sqlite3")
    canonical = store.create_memory(
        MemoryCreate(
            type="preference",
            content="The user prefers verified commands.",
            source_links=[
                SourceLinkCreate(label="First", kind="file", uri="file:///first.md")
            ],
        )
    )
    duplicate = store.create_memory(
        MemoryCreate(
            type="preference",
            content="The user prefers verified commands.",
            source_links=[
                SourceLinkCreate(label="Second", kind="file", uri="file:///second.md")
            ],
        )
    )

    run_id, proposals = store.preview_maintenance()
    proposal = next(item for item in proposals if item["type"] == "collapse_duplicate")

    assert run_id
    assert store.get_memory(duplicate.id).is_forgotten is False

    decided, affected = store.decide_maintenance(str(proposal["id"]), apply=True)

    assert decided["status"] == "applied"
    assert affected is not None and affected.is_forgotten is True
    assert {link.uri for link in store.get_memory(canonical.id).source_links} == {
        "file:///first.md",
        "file:///second.md",
    }
