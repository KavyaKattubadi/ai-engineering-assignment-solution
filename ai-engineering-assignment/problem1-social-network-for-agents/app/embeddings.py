"""
Embedding generation.

In production use OpenAI text-embedding-3-small (or a local model).
For demo / offline mode we fall back to a deterministic hash-based
pseudo-embedding so the rest of the pipeline remains testable.
"""

from typing import List
import hashlib
import struct
import numpy as np

from app.config import get_settings

settings = get_settings()


async def get_embedding(text: str) -> List[float]:
    """Return a 1536-dim embedding for the given text."""
    if settings.openai_api_key:
        return await _openai_embedding(text)
    return _fallback_embedding(text)


async def _openai_embedding(text: str) -> List[float]:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    resp = await client.embeddings.create(
        model=settings.embedding_model,
        input=text[:8000],  # safety truncate
    )
    return resp.data[0].embedding


def _fallback_embedding(text: str) -> List[float]:
    """
    Deterministic pseudo-embedding for local testing without API keys.
    Not semantically meaningful – only for plumbing tests.
    """
    dim = settings.embedding_dim
    seed = int(hashlib.sha256(text.encode()).hexdigest()[:16], 16)
    rng = np.random.RandomState(seed)
    vec = rng.randn(dim).astype(np.float32)
    # L2 normalise so cosine similarity behaves reasonably
    vec /= np.linalg.norm(vec) + 1e-9
    return vec.tolist()


def cosine_similarity(a: List[float], b: List[float]) -> float:
    a_np = np.array(a, dtype=np.float32)
    b_np = np.array(b, dtype=np.float32)
    return float(np.dot(a_np, b_np) / (np.linalg.norm(a_np) * np.linalg.norm(b_np) + 1e-9))