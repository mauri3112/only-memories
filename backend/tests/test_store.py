from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

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


def test_historical_non_axiom_cannot_create_a_branch(tmp_path):
    store = MemoryStore(tmp_path / "memories.sqlite3")
    original = store.create_memory(MemoryCreate(content="Use the first layout."))
    current = store.update_memory(
        original.id,
        MemoryUpdate(content="Use the second layout."),
    )

    with pytest.raises(ValueError, match="historical memory"):
        store.update_memory(
            original.id,
            MemoryUpdate(content="Create a competing second layout."),
        )
    with pytest.raises(ValueError, match="current memory"):
        store.create_memory(
            MemoryCreate(content="Create another branch.", supersedes_id=original.id)
        )

    history_current, versions = store.version_history_for_memory(original.id)

    assert history_current.id == current.id
    assert [version.id for version in versions if version.is_current] == [current.id]
    assert [version.version for version in versions] == [2, 1]


def test_content_edit_can_clear_source_links_and_metadata(tmp_path):
    store = MemoryStore(tmp_path / "memories.sqlite3")
    original = store.create_memory(
        MemoryCreate(
            content="Keep this source and metadata.",
            source_links=[
                SourceLinkCreate(label="Source", kind="file", uri="file:///source.md")
            ],
            metadata={"owner": "agent"},
        )
    )

    replacement = store.update_memory(
        original.id,
        MemoryUpdate(
            content="Remove this source and metadata.",
            source_links=[],
            metadata={},
        ),
    )

    assert replacement.source_links == []
    assert replacement.metadata == {}


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


def test_duplicate_cluster_proposals_share_one_canonical_target(tmp_path):
    store = MemoryStore(tmp_path / "memories.sqlite3")
    memories = [
        store.create_memory(
            MemoryCreate(
                type="preference",
                content="The user prefers one canonical memory.",
                source_links=[
                    SourceLinkCreate(
                        label=f"Source {index}",
                        kind="file",
                        uri=f"file:///source-{index}.md",
                    )
                ],
            )
        )
        for index in range(3)
    ]

    _, proposals = store.preview_maintenance()
    duplicate_proposals = [
        proposal for proposal in proposals if proposal["type"] == "collapse_duplicate"
    ]

    assert len(duplicate_proposals) == 2
    assert {proposal["target_id"] for proposal in duplicate_proposals} == {memories[0].id}
    assert {proposal["memory_id"] for proposal in duplicate_proposals} == {
        memories[1].id,
        memories[2].id,
    }

    for proposal in reversed(duplicate_proposals):
        store.decide_maintenance(str(proposal["id"]), apply=True)

    assert store.get_memory(memories[0].id).is_forgotten is False
    assert store.get_memory(memories[1].id).is_forgotten is True
    assert store.get_memory(memories[2].id).is_forgotten is True
    assert {link.uri for link in store.get_memory(memories[0].id).source_links} == {
        "file:///source-0.md",
        "file:///source-1.md",
        "file:///source-2.md",
    }


def test_axioms_cannot_be_forgotten_or_muted(tmp_path):
    store = MemoryStore(tmp_path / "memories.sqlite3")
    axiom = store.create_memory(
        MemoryCreate(type="axiom", axiom_key="identity", content="The user is Mauricio.")
    )

    with pytest.raises(ValueError, match="Axioms cannot be forgotten"):
        store.forget_memory(axiom.id, reason="should be impossible")
    with pytest.raises(ValueError, match="Axioms cannot be forgotten"):
        store.update_memory(axiom.id, MemoryUpdate(is_forgotten=True))

    assert store.get_memory(axiom.id).is_forgotten is False


def test_reinforce_connection_requires_existing_memories(tmp_path):
    store = MemoryStore(tmp_path / "memories.sqlite3")
    memory = store.create_memory(MemoryCreate(content="An existing memory."))

    with pytest.raises(KeyError):
        store.reinforce_connection(memory.id, "missing-target")
    with pytest.raises(KeyError):
        store.reinforce_connection("missing-source", memory.id)
