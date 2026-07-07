from __future__ import annotations

import hashlib
import math
import re

VECTOR_SIZE = 128
TOKEN_RE = re.compile(r"[a-zA-Z0-9_'-]+")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def embed_text(text: str, size: int = VECTOR_SIZE) -> list[float]:
    """Deterministic local embedding for offline development.

    This is not meant to compete with semantic embeddings. It gives the API a
    stable vector interface and useful-enough lexical similarity until a richer
    provider is plugged in.
    """

    vector = [0.0] * size
    for token in tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % size
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True))
