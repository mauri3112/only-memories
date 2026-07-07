from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    db_path: Path
    host: str
    port: int


def get_settings() -> Settings:
    root = Path(__file__).resolve().parents[1]
    db_path = Path(os.getenv("ONLY_MEMORIES_DB", root / "data" / "only-memories.sqlite3"))
    return Settings(
        db_path=db_path,
        host=os.getenv("ONLY_MEMORIES_HOST", "127.0.0.1"),
        port=int(os.getenv("ONLY_MEMORIES_PORT", "8765")),
    )
