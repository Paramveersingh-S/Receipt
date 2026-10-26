import hashlib
import math
import structlog
from typing import List
import numpy as np
from receipt_api.llm.client import get_llm_client

logger = structlog.get_logger(__name__)


def _deterministic_hash_vector(text: str, dim: int = 64) -> List[float]:
    """Generate a deterministic unit-length float vector from text for testing/offline mode."""
    vec = np.zeros(dim, dtype=np.float32)
    words = text.lower().split()
    if not words:
        words = ["empty"]
    for word in words:
        h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
        for i in range(dim):
            # pseudo-random projection based on word hash
            val = ((h >> (i % 32)) & 1) * 2 - 1
            vec[i] += val
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    a = np.array(vec1, dtype=np.float32)
    b = np.array(vec2, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


async def compute_embeddings(texts: List[str]) -> List[List[float]]:
    """Compute vector embeddings for a list of texts using LLMClient with deterministic fallback."""
    client = get_llm_client()
    try:
        return await client.embed(texts)
    except Exception as e:
        logger.warning("LLM embedding call failed, using deterministic embedding fallback", error=str(e))
        return [_deterministic_hash_vector(t) for t in texts]


def compute_embeddings_sync(texts: List[str]) -> List[List[float]]:
    """Synchronous wrapper for compute_embeddings."""
    import asyncio
    import concurrent.futures

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(compute_embeddings(texts))

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, compute_embeddings(texts)).result()
