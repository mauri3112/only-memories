from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from .embeddings import cosine_similarity, embed_text
from .ranking import rank_memory
from .schemas import (
    Cadence,
    Connection,
    ConnectionCreate,
    Memory,
    MemoryCreate,
    MemoryRelation,
    MemoryType,
    MemoryUpdate,
    SearchScope,
    SourceLink,
    SourceLinkCreate,
)

KEY_RE = re.compile(r"[^a-z0-9]+")


def utc_now() -> datetime:
    return datetime.now(UTC)


def normalize_axiom_key(content: str) -> str:
    words = KEY_RE.sub("-", content.lower()).strip("-").split("-")
    return "-".join(words[:8]) or "axiom"


class MemoryStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _init_db(self) -> None:
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    happened_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    cadence TEXT NOT NULL,
                    expires_at TEXT,
                    base_importance REAL NOT NULL,
                    access_count INTEGER NOT NULL DEFAULT 0,
                    axiom_key TEXT,
                    version INTEGER NOT NULL DEFAULT 1,
                    supersedes_id TEXT REFERENCES memories(id) ON DELETE SET NULL,
                    is_current INTEGER NOT NULL DEFAULT 1,
                    is_forgotten INTEGER NOT NULL DEFAULT 0,
                    forgotten_at TEXT,
                    forget_reason TEXT,
                    embedding TEXT NOT NULL,
                    metadata TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS connections (
                    source_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
                    target_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
                    weight REAL NOT NULL,
                    relation TEXT NOT NULL DEFAULT 'related',
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (source_id, target_id)
                );

                CREATE TABLE IF NOT EXISTS source_links (
                    id TEXT PRIMARY KEY,
                    memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
                    label TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    uri TEXT NOT NULL,
                    open_hint TEXT,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS maintenance_runs (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS maintenance_proposals (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES maintenance_runs(id) ON DELETE CASCADE,
                    type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
                    target_id TEXT REFERENCES memories(id) ON DELETE CASCADE,
                    reason TEXT NOT NULL,
                    score REAL,
                    created_at TEXT NOT NULL,
                    decided_at TEXT
                );
                """
            )
            self._ensure_column(db, "memories", "axiom_key", "TEXT")
            self._ensure_column(db, "memories", "version", "INTEGER NOT NULL DEFAULT 1")
            self._ensure_column(db, "memories", "supersedes_id", "TEXT")
            self._ensure_column(db, "memories", "is_current", "INTEGER NOT NULL DEFAULT 1")
            self._ensure_column(db, "memories", "is_forgotten", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(db, "memories", "forgotten_at", "TEXT")
            self._ensure_column(db, "memories", "forget_reason", "TEXT")
            self._ensure_column(db, "connections", "relation", "TEXT NOT NULL DEFAULT 'related'")

    def _ensure_column(
        self,
        db: sqlite3.Connection,
        table_name: str,
        column_name: str,
        column_definition: str,
    ) -> None:
        columns = {
            row["name"]
            for row in db.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name not in columns:
            db.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")

    def create_memory(self, payload: MemoryCreate) -> Memory:
        now = utc_now()
        memory_id = str(uuid.uuid4())
        happened_at = payload.happened_at or now
        embedding = embed_text(payload.content)
        memory_type = payload.type
        axiom_key = payload.axiom_key
        version = 1
        supersedes_id = payload.supersedes_id
        is_current = True
        expires_at = payload.expires_at
        cadence = payload.cadence

        with self.connect() as db:
            if memory_type == MemoryType.axiom:
                axiom_key = axiom_key or normalize_axiom_key(payload.content)
                expires_at = None
                cadence = Cadence.none
                previous = self._current_axiom_row(db, axiom_key)
                if previous:
                    supersedes_id = previous["id"]
                    version = int(previous["version"]) + 1
                    self._mark_superseded(db, supersedes_id, now)
            elif supersedes_id:
                previous = db.execute(
                    "SELECT id, version FROM memories WHERE id = ?",
                    (supersedes_id,),
                ).fetchone()
                if previous is None:
                    raise KeyError(supersedes_id)
                version = int(previous["version"]) + 1
                self._mark_superseded(db, supersedes_id, now)

            db.execute(
                """
                INSERT INTO memories (
                    id, type, content, happened_at, created_at, updated_at, source,
                    cadence, expires_at, base_importance, access_count, axiom_key, version,
                    supersedes_id, is_current, embedding, metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    memory_type.value,
                    payload.content,
                    happened_at.isoformat(),
                    now.isoformat(),
                    now.isoformat(),
                    payload.source,
                    cadence.value,
                    expires_at.isoformat() if expires_at else None,
                    payload.base_importance,
                    axiom_key,
                    version,
                    supersedes_id,
                    int(is_current),
                    json.dumps(embedding),
                    json.dumps(payload.metadata),
                ),
            )
            for source_link in payload.source_links:
                self._insert_source_link(db, memory_id, source_link)
            for connection in payload.connections:
                self._upsert_connection(db, memory_id, connection)
            if supersedes_id:
                self._upsert_connection(
                    db,
                    memory_id,
                    ConnectionCreate(
                        target_id=supersedes_id,
                        weight=0.95,
                        relation=MemoryRelation.updates,
                        reason="supersedes",
                    ),
                )

        self.suggest_connections(memory_id)
        return self.get_memory(memory_id)

    def update_memory(self, memory_id: str, payload: MemoryUpdate) -> Memory:
        memory = self.get_memory(memory_id)
        if payload.content is not None and payload.content != memory.content:
            source_links = payload.source_links or [
                SourceLinkCreate(
                    label=link.label,
                    kind=link.kind,
                    uri=link.uri,
                    open_hint=link.open_hint,
                    metadata=link.metadata,
                )
                for link in memory.source_links
            ]
            return self.create_memory(
                MemoryCreate(
                    type=memory.type,
                    content=payload.content,
                    happened_at=memory.happened_at,
                    source=memory.source,
                    source_links=source_links,
                    cadence=payload.cadence or memory.cadence,
                    expires_at=(
                        payload.expires_at
                        if payload.expires_at is not None
                        else memory.expires_at
                    ),
                    base_importance=(
                        payload.base_importance
                        if payload.base_importance is not None
                        else memory.base_importance
                    ),
                    axiom_key=memory.axiom_key,
                    supersedes_id=memory.id,
                    metadata=payload.metadata or memory.metadata,
                )
            )
        content = payload.content if payload.content is not None else memory.content
        metadata = payload.metadata if payload.metadata is not None else memory.metadata
        cadence = payload.cadence if payload.cadence is not None else memory.cadence
        expires_at = payload.expires_at if payload.expires_at is not None else memory.expires_at
        base_importance = (
            payload.base_importance
            if payload.base_importance is not None
            else memory.base_importance
        )
        is_forgotten = (
            payload.is_forgotten if payload.is_forgotten is not None else memory.is_forgotten
        )
        forgotten_at = memory.forgotten_at
        forget_reason = memory.forget_reason
        now = utc_now()
        if payload.is_forgotten is True and not memory.is_forgotten:
            forgotten_at = now
            forget_reason = payload.forget_reason
        elif payload.is_forgotten is False:
            forgotten_at = None
            forget_reason = None
        elif payload.forget_reason is not None:
            forget_reason = payload.forget_reason

        with self.connect() as db:
            db.execute(
                """
                UPDATE memories
                SET content = ?, cadence = ?, expires_at = ?, base_importance = ?,
                    is_forgotten = ?, forgotten_at = ?, forget_reason = ?,
                    metadata = ?, embedding = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    content,
                    cadence.value,
                    expires_at.isoformat() if expires_at else None,
                    base_importance,
                    int(is_forgotten),
                    forgotten_at.isoformat() if forgotten_at else None,
                    forget_reason,
                    json.dumps(metadata),
                    json.dumps(embed_text(content)),
                    now.isoformat(),
                    memory_id,
                ),
            )
            if payload.source_links is not None:
                db.execute("DELETE FROM source_links WHERE memory_id = ?", (memory_id,))
                for source_link in payload.source_links:
                    self._insert_source_link(db, memory_id, source_link)
        self.suggest_connections(memory_id)
        return self.get_memory(memory_id)

    def forget_memory(self, memory_id: str, reason: str | None = None) -> Memory:
        self.get_memory(memory_id)
        now = utc_now()
        with self.connect() as db:
            db.execute(
                """
                UPDATE memories
                SET is_forgotten = 1, forgotten_at = ?, forget_reason = ?, updated_at = ?
                WHERE id = ?
                """,
                (now.isoformat(), reason, now.isoformat(), memory_id),
            )
        return self.get_memory(memory_id)

    def restore_memory(self, memory_id: str) -> Memory:
        self.get_memory(memory_id)
        now = utc_now()
        with self.connect() as db:
            db.execute(
                """
                UPDATE memories
                SET is_forgotten = 0, forgotten_at = NULL, forget_reason = NULL, updated_at = ?
                WHERE id = ?
                """,
                (now.isoformat(), memory_id),
            )
        return self.get_memory(memory_id)

    def get_memory(self, memory_id: str) -> Memory:
        with self.connect() as db:
            row = db.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
            if row is None:
                raise KeyError(memory_id)
            return self._row_to_memory(row)

    def list_memories(
        self,
        limit: int = 50,
        memory_type: str | None = None,
        *,
        include_versions: bool = False,
        include_forgotten: bool = False,
        include_expired: bool = False,
    ) -> list[Memory]:
        filters = []
        params: list[object] = []
        if memory_type:
            filters.append("type = ?")
            params.append(memory_type)
        if not include_versions:
            filters.append("is_current = 1")
        if not include_forgotten:
            filters.append("is_forgotten = 0")
        if not include_expired:
            filters.append("(expires_at IS NULL OR expires_at > ?)")
            params.append(utc_now().isoformat())
        where_clause = " AND ".join(filters) if filters else "1 = 1"
        params.append(limit)

        with self.connect() as db:
            rows = db.execute(
                f"""
                SELECT * FROM memories
                WHERE {where_clause}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [self._with_rank(memory) for memory in map(self._row_to_memory, rows)]

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        memory_type: str | None = None,
        scope: SearchScope = SearchScope.general,
        include_forgotten: bool = False,
        include_expired: bool = False,
    ) -> list[Memory]:
        query_embedding = embed_text(query)
        memories = self.list_memories(
            limit=500,
            memory_type=memory_type,
            include_versions=scope == SearchScope.remembering,
            include_forgotten=include_forgotten,
            include_expired=include_expired,
        )
        centrality = self.centrality_scores()

        ranked = []
        for memory in memories:
            similarity = cosine_similarity(query_embedding, self.embedding_for(memory.id))
            memory.rank = rank_memory(
                memory,
                similarity=max(similarity, 0),
                centrality=centrality.get(memory.id, 0),
            )
            ranked.append(memory)

        ranked.sort(key=lambda item: item.rank or 0, reverse=True)
        return ranked[:limit]

    def navigate(self, memory_id: str, limit: int = 10) -> tuple[Memory, list[Memory]]:
        origin = self.get_memory(memory_id)
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT m.*, c.weight
                FROM connections c
                JOIN memories m ON m.id = c.target_id
                WHERE c.source_id = ?
                  AND m.is_current = 1
                  AND m.is_forgotten = 0
                  AND (m.expires_at IS NULL OR m.expires_at > ?)
                ORDER BY c.weight DESC
                LIMIT ?
                """,
                (memory_id, utc_now().isoformat(), limit),
            ).fetchall()
        memories = []
        for row in rows:
            memory = self._row_to_memory(row)
            memory.rank = rank_memory(memory, centrality=float(row["weight"]))
            memories.append(memory)
        self.touch(memory_id)
        return origin, memories

    def graph_for(self, memory_id: str, limit: int = 10) -> tuple[Memory, list[Memory], list[Connection]]:
        origin = self.get_memory(memory_id)
        edges = self.connections_for(memory_id)[:limit]
        nodes = []
        for edge in edges:
            try:
                memory = self.get_memory(edge.target_id)
            except KeyError:
                continue
            if memory.is_current and not memory.is_forgotten and (
                memory.expires_at is None or memory.expires_at > utc_now()
            ):
                nodes.append(self._with_rank(memory))
        self.touch(memory_id)
        return origin, nodes, edges

    def preview_maintenance(self) -> tuple[str, list[dict[str, object]]]:
        run_id = str(uuid.uuid4())
        now = utc_now()
        proposals: list[dict[str, object]] = []
        with self.connect() as db:
            db.execute(
                "INSERT INTO maintenance_runs (id, created_at) VALUES (?, ?)",
                (run_id, now.isoformat()),
            )
            rows = db.execute(
                "SELECT * FROM memories WHERE is_current = 1 AND is_forgotten = 0"
            ).fetchall()
            memories = [self._row_to_memory(row) for row in rows]
            for memory in memories:
                if memory.expires_at and memory.expires_at <= now:
                    proposals.append(
                        self._proposal_dict(
                            run_id,
                            "retire_expired",
                            memory.id,
                            "The memory has passed its expiration date.",
                        )
                    )

            for index, memory in enumerate(memories):
                normalized = " ".join(memory.content.lower().split())
                for candidate in memories[index + 1 :]:
                    if memory.type != candidate.type:
                        continue
                    candidate_normalized = " ".join(candidate.content.lower().split())
                    similarity = cosine_similarity(
                        self.embedding_for(memory.id), self.embedding_for(candidate.id)
                    )
                    if normalized == candidate_normalized or similarity >= 0.92:
                        canonical, duplicate = sorted(
                            (memory, candidate),
                            key=lambda item: (item.created_at, item.id),
                        )
                        proposals.append(
                            self._proposal_dict(
                                run_id,
                                "collapse_duplicate",
                                duplicate.id,
                                "Same-type memories are near duplicates; keep the older canonical record.",
                                target_id=canonical.id,
                                score=round(similarity, 4),
                            )
                        )
                        break

            proposed_pairs = {
                tuple(sorted((str(item["memory_id"]), str(item["target_id"]))))
                for item in proposals
                if item["target_id"]
            }
            connection_count = 0
            for index, memory in enumerate(memories):
                for candidate in memories[index + 1 :]:
                    pair = tuple(sorted((memory.id, candidate.id)))
                    if pair in proposed_pairs:
                        continue
                    exists = db.execute(
                        """SELECT 1 FROM connections
                           WHERE (source_id = ? AND target_id = ?)
                              OR (source_id = ? AND target_id = ?)""",
                        (memory.id, candidate.id, candidate.id, memory.id),
                    ).fetchone()
                    if exists:
                        continue
                    similarity = cosine_similarity(
                        self.embedding_for(memory.id), self.embedding_for(candidate.id)
                    )
                    if similarity >= 0.35:
                        proposals.append(
                            self._proposal_dict(
                                run_id,
                                "add_connection",
                                memory.id,
                                "Similar memories have no graph connection.",
                                target_id=candidate.id,
                                score=round(similarity, 4),
                            )
                        )
                        connection_count += 1
                        if connection_count >= 10:
                            break
                if connection_count >= 10:
                    break

            for proposal in proposals:
                db.execute(
                    """
                    INSERT INTO maintenance_proposals (
                        id, run_id, type, status, memory_id, target_id, reason, score, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        proposal["id"], proposal["run_id"], proposal["type"],
                        proposal["status"], proposal["memory_id"], proposal["target_id"],
                        proposal["reason"], proposal["score"], proposal["created_at"],
                    ),
                )
        return run_id, proposals

    def maintenance_proposals(self, run_id: str | None = None) -> list[dict[str, object]]:
        with self.connect() as db:
            if run_id:
                rows = db.execute(
                    "SELECT * FROM maintenance_proposals WHERE run_id = ? ORDER BY created_at",
                    (run_id,),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM maintenance_proposals ORDER BY created_at DESC"
                ).fetchall()
        return [dict(row) for row in rows]

    def decide_maintenance(self, proposal_id: str, *, apply: bool) -> tuple[dict[str, object], Memory | None]:
        now = utc_now()
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM maintenance_proposals WHERE id = ?", (proposal_id,)
            ).fetchone()
            if row is None:
                raise KeyError(proposal_id)
            if row["status"] != "pending":
                raise ValueError("Maintenance proposal has already been decided")
            affected: Memory | None = None
            if apply:
                if row["type"] == "retire_expired":
                    db.execute(
                        """UPDATE memories SET is_forgotten = 1, forgotten_at = ?,
                           forget_reason = ?, updated_at = ? WHERE id = ?""",
                        (now.isoformat(), "maintenance: expired", now.isoformat(), row["memory_id"]),
                    )
                elif row["type"] == "collapse_duplicate":
                    self._collapse_duplicate(db, row["memory_id"], row["target_id"], now)
                elif row["type"] == "add_connection":
                    self._upsert_connection(
                        db,
                        row["memory_id"],
                        ConnectionCreate(
                            target_id=row["target_id"],
                            weight=row["score"] or 0.35,
                            relation=MemoryRelation.related,
                            reason="approved maintenance suggestion",
                        ),
                    )
                    self._upsert_connection(
                        db,
                        row["target_id"],
                        ConnectionCreate(
                            target_id=row["memory_id"],
                            weight=row["score"] or 0.35,
                            relation=MemoryRelation.related,
                            reason="approved maintenance suggestion",
                        ),
                    )
                status = "applied"
            else:
                status = "dismissed"
            db.execute(
                "UPDATE maintenance_proposals SET status = ?, decided_at = ? WHERE id = ?",
                (status, now.isoformat(), proposal_id),
            )
        if apply:
            affected = self.get_memory(row["memory_id"])
        proposal = self.maintenance_proposals(row["run_id"])
        return next(item for item in proposal if item["id"] == proposal_id), affected

    def _proposal_dict(
        self,
        run_id: str,
        proposal_type: str,
        memory_id: str,
        reason: str,
        *,
        target_id: str | None = None,
        score: float | None = None,
    ) -> dict[str, object]:
        return {
            "id": str(uuid.uuid4()), "run_id": run_id, "type": proposal_type,
            "status": "pending", "memory_id": memory_id, "target_id": target_id,
            "reason": reason, "score": score, "created_at": utc_now().isoformat(),
            "decided_at": None,
        }

    def _collapse_duplicate(
        self, db: sqlite3.Connection, duplicate_id: str, canonical_id: str, now: datetime
    ) -> None:
        links = db.execute(
            "SELECT * FROM source_links WHERE memory_id = ?", (duplicate_id,)
        ).fetchall()
        existing = {
            (row["kind"], row["uri"])
            for row in db.execute(
                "SELECT kind, uri FROM source_links WHERE memory_id = ?", (canonical_id,)
            ).fetchall()
        }
        for link in links:
            if (link["kind"], link["uri"]) not in existing:
                db.execute(
                    "UPDATE source_links SET memory_id = ? WHERE id = ?", (canonical_id, link["id"])
                )
        edges = db.execute(
            "SELECT * FROM connections WHERE source_id = ?", (duplicate_id,)
        ).fetchall()
        for edge in edges:
            if edge["target_id"] in {duplicate_id, canonical_id}:
                continue
            self._upsert_connection(
                db,
                canonical_id,
                ConnectionCreate(
                    target_id=edge["target_id"], weight=edge["weight"],
                    relation=edge["relation"], reason="merged duplicate: " + edge["reason"],
                ),
            )
        db.execute(
            """UPDATE memories SET is_forgotten = 1, forgotten_at = ?, forget_reason = ?,
               updated_at = ? WHERE id = ?""",
            (now.isoformat(), f"maintenance: duplicate of {canonical_id}", now.isoformat(), duplicate_id),
        )

    def connections_for(self, memory_id: str) -> list[Connection]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM connections WHERE source_id = ? ORDER BY weight DESC",
                (memory_id,),
            ).fetchall()
        return [self._row_to_connection(row) for row in rows]

    def source_links_for(self, memory_id: str) -> list[SourceLink]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM source_links WHERE memory_id = ? ORDER BY created_at DESC",
                (memory_id,),
            ).fetchall()
        return [self._row_to_source_link(row) for row in rows]

    def version_history_for_memory(self, memory_id: str) -> tuple[Memory, list[Memory]]:
        memory = self.get_memory(memory_id)
        if memory.type != MemoryType.axiom or not memory.axiom_key:
            return self.version_history_for_chain(memory_id)
        return self.version_history_for_axiom(memory.axiom_key)

    def version_history_for_chain(self, memory_id: str) -> tuple[Memory, list[Memory]]:
        with self.connect() as db:
            row = db.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
            if row is None:
                raise KeyError(memory_id)

            rows_by_id: dict[str, sqlite3.Row] = {row["id"]: row}
            visited = {row["id"]}
            cursor = row
            while cursor["supersedes_id"] and cursor["supersedes_id"] not in visited:
                parent = db.execute(
                    "SELECT * FROM memories WHERE id = ?",
                    (cursor["supersedes_id"],),
                ).fetchone()
                if parent is None:
                    break
                rows_by_id[parent["id"]] = parent
                visited.add(parent["id"])
                cursor = parent

            cursor = row
            while True:
                child = db.execute(
                    """
                    SELECT *
                    FROM memories
                    WHERE supersedes_id = ?
                    ORDER BY version ASC, updated_at ASC
                    LIMIT 1
                    """,
                    (cursor["id"],),
                ).fetchone()
                if child is None or child["id"] in visited:
                    break
                rows_by_id[child["id"]] = child
                visited.add(child["id"])
                cursor = child

        versions = [self._row_to_memory(row) for row in rows_by_id.values()]
        versions.sort(key=lambda item: (item.version, item.updated_at), reverse=True)
        current = next((memory for memory in versions if memory.is_current), versions[0])
        return current, versions

    def version_history_for_axiom(self, axiom_key: str) -> tuple[Memory, list[Memory]]:
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT *
                FROM memories
                WHERE type = ? AND axiom_key = ?
                ORDER BY version DESC, happened_at DESC
                """,
                (MemoryType.axiom.value, axiom_key),
            ).fetchall()
        if not rows:
            raise KeyError(axiom_key)
        versions = [self._row_to_memory(row) for row in rows]
        current = next((memory for memory in versions if memory.is_current), versions[0])
        return current, versions

    def reinforce_connection(
        self,
        source_id: str,
        target_id: str,
        *,
        amount: float = 0.1,
        reason: str = "reinforced",
    ) -> None:
        with self.connect() as db:
            existing = db.execute(
                "SELECT weight FROM connections WHERE source_id = ? AND target_id = ?",
                (source_id, target_id),
            ).fetchone()
            if existing:
                db.execute(
                    """
                    UPDATE connections
                    SET weight = MIN(weight + ?, 1.0), reason = ?
                    WHERE source_id = ? AND target_id = ?
                    """,
                    (amount, reason, source_id, target_id),
                )
            else:
                db.execute(
                    """
                    INSERT INTO connections (source_id, target_id, weight, relation, reason, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_id,
                        target_id,
                        min(amount, 1.0),
                        MemoryRelation.related.value,
                        reason,
                        utc_now().isoformat(),
                    ),
                )

    def suggest_connections(self, memory_id: str, threshold: float = 0.22, limit: int = 8) -> None:
        source_embedding = self.embedding_for(memory_id)
        candidates: list[tuple[str, float]] = []
        for memory in self.list_memories(limit=500):
            if memory.id == memory_id:
                continue
            similarity = cosine_similarity(source_embedding, self.embedding_for(memory.id))
            if similarity >= threshold:
                candidates.append((memory.id, similarity))

        candidates.sort(key=lambda item: item[1], reverse=True)
        with self.connect() as db:
            for target_id, similarity in candidates[:limit]:
                weight = round(min(max(similarity, 0.05), 0.95), 4)
                self._upsert_connection(
                    db,
                    memory_id,
                    ConnectionCreate(
                        target_id=target_id,
                        weight=weight,
                        relation=MemoryRelation.related,
                        reason="similarity",
                    ),
                )
                self._upsert_connection(
                    db,
                    target_id,
                    ConnectionCreate(
                        target_id=memory_id,
                        weight=weight,
                        relation=MemoryRelation.related,
                        reason="similarity",
                    ),
                )

    def touch(self, memory_id: str) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE memories SET access_count = access_count + 1 WHERE id = ?",
                (memory_id,),
            )

    def embedding_for(self, memory_id: str) -> list[float]:
        with self.connect() as db:
            row = db.execute("SELECT embedding FROM memories WHERE id = ?", (memory_id,)).fetchone()
            if row is None:
                raise KeyError(memory_id)
            return json.loads(row["embedding"])

    def centrality_scores(self) -> dict[str, float]:
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT target_id, SUM(weight) AS total
                FROM connections c
                JOIN memories m ON m.id = c.target_id
                WHERE m.is_current = 1
                  AND m.is_forgotten = 0
                  AND (m.expires_at IS NULL OR m.expires_at > ?)
                GROUP BY target_id
                """,
                (utc_now().isoformat(),),
            ).fetchall()

        if not rows:
            return {}
        max_total = max(float(row["total"]) for row in rows) or 1.0
        return {row["target_id"]: float(row["total"]) / max_total for row in rows}

    def _insert_source_link(
        self,
        db: sqlite3.Connection,
        memory_id: str,
        source_link: SourceLinkCreate,
    ) -> None:
        db.execute(
            """
            INSERT INTO source_links (
                id, memory_id, label, kind, uri, open_hint, metadata, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                memory_id,
                source_link.label,
                source_link.kind,
                source_link.uri,
                source_link.open_hint,
                json.dumps(source_link.metadata),
                utc_now().isoformat(),
            ),
        )

    def _upsert_connection(
        self,
        db: sqlite3.Connection,
        source_id: str,
        connection: ConnectionCreate,
    ) -> None:
        if source_id == connection.target_id:
            return
        db.execute(
            """
            INSERT INTO connections (source_id, target_id, weight, relation, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id, target_id) DO UPDATE SET
                weight = MAX(connections.weight, excluded.weight),
                relation = CASE
                    WHEN connections.relation != 'related' AND excluded.relation = 'related'
                    THEN connections.relation
                    ELSE excluded.relation
                END,
                reason = CASE
                    WHEN connections.relation != 'related' AND excluded.relation = 'related'
                    THEN connections.reason
                    ELSE excluded.reason
                END
            """,
            (
                source_id,
                connection.target_id,
                connection.weight,
                connection.relation.value,
                connection.reason,
                utc_now().isoformat(),
            ),
        )

    def _current_axiom_row(self, db: sqlite3.Connection, axiom_key: str) -> sqlite3.Row | None:
        return db.execute(
            """
            SELECT id, version
            FROM memories
            WHERE type = ? AND axiom_key = ? AND is_current = 1
            ORDER BY version DESC
            LIMIT 1
            """,
            (MemoryType.axiom.value, axiom_key),
        ).fetchone()

    def _mark_superseded(
        self,
        db: sqlite3.Connection,
        memory_id: str,
        now: datetime,
    ) -> None:
        db.execute(
            "UPDATE memories SET is_current = 0, updated_at = ? WHERE id = ?",
            (now.isoformat(), memory_id),
        )

    def _row_to_memory(self, row: sqlite3.Row) -> Memory:
        return Memory(
            id=row["id"],
            type=row["type"],
            content=row["content"],
            happened_at=datetime.fromisoformat(row["happened_at"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            source=row["source"],
            source_links=self.source_links_for(row["id"]),
            cadence=Cadence(row["cadence"]),
            expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
            base_importance=float(row["base_importance"]),
            access_count=int(row["access_count"]),
            axiom_key=row["axiom_key"],
            version=int(row["version"]),
            supersedes_id=row["supersedes_id"],
            is_current=bool(row["is_current"]),
            is_forgotten=bool(row["is_forgotten"]),
            forgotten_at=datetime.fromisoformat(row["forgotten_at"]) if row["forgotten_at"] else None,
            forget_reason=row["forget_reason"],
            metadata=json.loads(row["metadata"]),
        )

    def _row_to_source_link(self, row: sqlite3.Row) -> SourceLink:
        return SourceLink(
            id=row["id"],
            memory_id=row["memory_id"],
            label=row["label"],
            kind=row["kind"],
            uri=row["uri"],
            open_hint=row["open_hint"],
            metadata=json.loads(row["metadata"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def _row_to_connection(self, row: sqlite3.Row) -> Connection:
        return Connection(
            source_id=row["source_id"],
            target_id=row["target_id"],
            weight=float(row["weight"]),
            relation=MemoryRelation(row["relation"]),
            reason=row["reason"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def _with_rank(self, memory: Memory) -> Memory:
        memory.rank = rank_memory(memory, centrality=self.centrality_scores().get(memory.id, 0))
        return memory
