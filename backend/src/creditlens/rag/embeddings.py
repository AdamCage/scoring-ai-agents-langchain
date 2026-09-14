from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence

import numpy as np

from creditlens.llm.routerai import embeddings_model


def _hash_vector(text: str, dim: int = 64) -> list[float]:
    vec = np.zeros(dim, dtype=float)
    tokens = [tok for tok in text.lower().replace("\n", " ").split(" ") if tok]
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:2], "little") % dim
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vec[idx] += sign
    norm = np.linalg.norm(vec)
    if norm:
        vec = vec / norm
    return vec.tolist()


def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    model = embeddings_model()
    if model is None:
        return [_hash_vector(text) for text in texts]
    return model.embed_documents(list(texts))


def embed_query(text: str) -> list[float]:
    model = embeddings_model()
    if model is None:
        return _hash_vector(text)
    return model.embed_query(text)


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if not na or not nb:
        return 0.0
    return dot / (na * nb)
