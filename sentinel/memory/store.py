"""SQLite-backed memory store for Sentinel Memory.

Provides persistent storage for memories with temporal queries,
tag-based filtering, and expiration support.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .models import Memory, MemoryType

_MEMORY_DDL = """
    CREATE TABLE IF NOT EXISTS memories (
        id TEXT PRIMARY KEY,
        type TEXT,
        content TEXT,
        confidence REAL,
        created_at TEXT,
        last_used_at TEXT,
        expires_at TEXT,
        source TEXT,
        tags TEXT
    )
"""


class MemoryStore:
    """SQLite-backed persistent memory storage.

    Usage:
        store = MemoryStore("./memory.db")
        store.insert(memory)
        results = store.query(tags=["python"], type=MemoryType.RULE)
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(_MEMORY_DDL)

    def insert(self, memory: Memory) -> None:
        """Insert a memory into the store."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO memories
                   (id, type, content, confidence, created_at, last_used_at,
                    expires_at, source, tags)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    memory.id,
                    memory.type.value,
                    json.dumps(memory.content),
                    memory.confidence,
                    memory.created_at,
                    memory.last_used_at,
                    memory.expires_at,
                    memory.source,
                    json.dumps(memory.tags),
                ),
            )

    def get(self, memory_id: str) -> Memory | None:
        """Retrieve a memory by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()

        if row is None:
            return None

        return self._row_to_memory(row)

    def update(self, memory_id: str, updates: dict[str, Any]) -> bool:
        """Update fields on a memory. Returns True if updated."""
        memory = self.get(memory_id)
        if memory is None:
            return False

        for key, value in updates.items():
            if hasattr(memory, key):
                setattr(memory, key, value)

        self.insert(memory)
        return True

    def delete(self, memory_id: str) -> bool:
        """Delete a memory. Returns True if deleted."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            return cursor.rowcount > 0

    def list_all(self) -> list[Memory]:
        """Return all memories."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM memories ORDER BY created_at DESC").fetchall()

        return [self._row_to_memory(row) for row in rows]

    def query(
        self,
        tags: list[str] | None = None,
        type: MemoryType | None = None,
        min_confidence: float = 0.0,
        include_expired: bool = False,
    ) -> list[Memory]:
        """Query memories with filters.

        Args:
            tags: Filter by tags (AND logic — all must match).
            type: Filter by memory type.
            min_confidence: Minimum confidence threshold.
            include_expired: If False, exclude expired memories.
        """
        conditions: list[str] = []
        params: list[Any] = []

        if type:
            conditions.append("type = ?")
            params.append(type.value)

        if min_confidence > 0:
            conditions.append("confidence >= ?")
            params.append(min_confidence)

        if not include_expired:
            conditions.append("(expires_at IS NULL OR expires_at > ?)")
            params.append(_now_iso())

        query = "SELECT * FROM memories"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY confidence DESC, created_at DESC"

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()

        memories = [self._row_to_memory(row) for row in rows]

        if tags:
            tag_set = set(tags)
            memories = [m for m in memories if tag_set.issubset(m.tags)]

        return memories

    def count(self) -> int:
        """Return total number of memories."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT COUNT(*) FROM memories").fetchone()
            return row[0] if row else 0

    def touch(self, memory_id: str) -> bool:
        """Update last_used_at timestamp. Returns True if updated."""
        return self.update(memory_id, {"last_used_at": _now_iso()})

    def _row_to_memory(self, row: sqlite3.Row) -> Memory:
        """Convert a database row to a Memory object."""
        return Memory(
            id=row["id"],
            type=MemoryType(row["type"]),
            content=json.loads(row["content"] or "{}"),
            confidence=row["confidence"],
            created_at=row["created_at"],
            last_used_at=row["last_used_at"],
            expires_at=row["expires_at"],
            source=row["source"],
            tags=json.loads(row["tags"] or "[]"),
        )


def _now_iso() -> str:
    """Return current UTC time as ISO string."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
