from __future__ import annotations

import math
from datetime import UTC, datetime

from .schemas import Cadence, Memory, MemoryType

CADENCE_BOOSTS = {
    Cadence.none: 0.0,
    Cadence.daily: 0.16,
    Cadence.weekly: 0.10,
    Cadence.monthly: 0.06,
    Cadence.seasonal: 0.03,
}


def age_days(memory: Memory, now: datetime | None = None) -> float:
    now = now or datetime.now(UTC)
    return max((now - memory.happened_at).total_seconds() / 86_400, 0)


def time_factor(memory: Memory, now: datetime | None = None) -> float:
    now = now or datetime.now(UTC)
    if memory.type == MemoryType.axiom:
        return 1.1 if memory.is_current else 0.55

    if memory.expires_at and memory.expires_at <= now:
        return 0.0

    days = age_days(memory, now)
    decay = math.exp(-days / 180)
    cadence = CADENCE_BOOSTS.get(memory.cadence, 0.0)
    return min(decay + cadence, 1.2)


def rank_memory(
    memory: Memory,
    *,
    similarity: float = 0.0,
    centrality: float = 0.0,
    now: datetime | None = None,
) -> float:
    access_boost = min(memory.access_count * 0.015, 0.15)
    return round(
        (similarity * 0.44)
        + (memory.base_importance * 0.24)
        + (time_factor(memory, now) * 0.14)
        + (centrality * 0.14)
        + access_boost,
        6,
    )
