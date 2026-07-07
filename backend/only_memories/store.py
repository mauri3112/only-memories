from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from .embeddings import cosine_similarity, embed_text
from .ranking import rank_memory
from .schemas import Cadence, Connection, ConnectionCreate, Memory, MemoryCreate, MemoryUpdate


def utc_now() -> datetime:
    return datetime.now(UTC)


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
                    embedding TEXT NOT NULL,
                    metadata TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS connections (
                    source_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
                    target_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
                    weight REAL NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (source_id, target_id)
                );
                """
            )

    def create_memory(self, payload: MemoryCreate) -> Memory:
        now = utc_now()
        memory_id = str(uuid.uuid4())
        happened_at = payload.happened_at or now
        embedding = embed_text(payload.content)
        with self.connect() as db:
            db.execute(
                """
                INSERT INTO memories (
                    id, type, content, happened_at, created_at, updated_at, source,
                    cadence, expires_at, base_importance, access_count, embedding, metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    memory_id,
                    payload.type.value,
                    payload.content,
                    happened_at.isoformat(),
                    now.isoformat(),
                    now.isoformat(),
                    payload.source,
                    payload.cadence.value,
                    payload.expires_at.isoformat() if payload.expires_at else None,
                    payload.base_importance,
                    json.dumps(embedding),
                    json.dumps(payload.metadata),
                ),
            )
            for connection in payload.connections:
                self._upsert_connection(db, memory_id, connection)

        self.suggest_connections(memory_id)
        return self.get_memory(memory_id)

    def update_memory(self, memory_id: str, payload: MemoryUpdate) -> Memory:
        memory = self.get_memory(memory_id)
        content = payload.content if payload.content is not None else memory.content
        metadata = payload.metadata if payload.metadata is not None else memory.metadata
        cadence = payload.cadence if payload.cadence is not None else memory.cadence
        expires_at = payload.expires_at if payload.expires_at is not None else memory.expires_at
        base_importance = (
            payload.base_importance
            if payload.base_importance is not None
            else memory.base_importance
        )
        now = utc_now()

        with self.connect() as db:
            db.execute(
                """
                UPDATE memories
                SET content = ?, cadence = ?, expires_at = ?, base_importance = ?,
                    metadata = ?, embedding = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    content,
                    cadence.value,
                    expires_at.isoformat() if expires_at else None,
                    base_importance,
                    json.dumps(metadata),
                    json.dumps(embed_text(content)),
                    now.isoformat(),
                    memory_id,
                ),
            )
        self.suggest_connections(memory_id)
        return self.get_memory(memory_id)

    def get_memory(self, memory_id: str) -> Memory:
        with self.connect() as db:
            row = db.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
            if row is None:
                raise KeyError(memory_id)
            return self._row_to_memory(row)

    def list_memories(self, limit: int = 50, memory_type: str | None = None) -> list[Memory]:
        with self.connect() as db:
            if memory_type:
                rows = db.execute(
                    "SELECT * FROM memories WHERE type = ? ORDER BY updated_at DESC LIMIT ?",
                    (memory_type, limit),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM memories ORDER BY updated_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [self._with_rank(memory) for memory in map(self._row_to_memory, rows)]

    def search(self, query: str, *, limit: int = 10, memory_type: str | None = None) -> list[Memory]:
        query_embedding = embed_text(query)
        memories = self.list_memories(limit=500, memory_type=memory_type)
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
                ORDER BY c.weight DESC
                LIMIT ?
                """,
                (memory_id, limit),
            ).fetchall()
        memories = []
        for row in rows:
            memory = self._row_to_memory(row)
            memory.rank = rank_memory(memory, centrality=float(row["weight"]))
            memories.append(memory)
        self.touch(memory_id)
        return origin, memories

    def connections_for(self, memory_id: str) -> list[Connection]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM connections WHERE source_id = ? ORDER BY weight DESC",
                (memory_id,),
            ).fetchall()
        return [self._row_to_connection(row) for row in rows]

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
                    INSERT INTO connections (source_id, target_id, weight, reason, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (source_id, target_id, min(amount, 1.0), reason, utc_now().isoformat()),
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
                    ConnectionCreate(target_id=target_id, weight=weight, reason="similarity"),
                )
                self._upsert_connection(
                    db,
                    target_id,
                    ConnectionCreate(target_id=memory_id, weight=weight, reason="similarity"),
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
                FROM connections
                GROUP BY target_id
                """
            ).fetchall()

        if not rows:
            return {}
        max_total = max(float(row["total"]) for row in rows) or 1.0
        return {row["target_id"]: float(row["total"]) / max_total for row in rows}

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
            INSERT INTO connections (source_id, target_id, weight, reason, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source_id, target_id) DO UPDATE SET
                weight = MAX(connections.weight, excluded.weight),
                reason = excluded.reason
            """,
            (
                source_id,
                connection.target_id,
                connection.weight,
                connection.reason,
                utc_now().isoformat(),
            ),
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
            cadence=Cadence(row["cadence"]),
            expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
            base_importance=float(row["base_importance"]),
            access_count=int(row["access_count"]),
            metadata=json.loads(row["metadata"]),
        )

    def _row_to_connection(self, row: sqlite3.Row) -> Connection:
        return Connection(
            source_id=row["source_id"],
            target_id=row["target_id"],
            weight=float(row["weight"]),
            reason=row["reason"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def _with_rank(self, memory: Memory) -> Memory:
        memory.rank = rank_memory(memory, centrality=self.centrality_scores().get(memory.id, 0))
        return memory
