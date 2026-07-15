"""Dense embedding utilities — AI Gateway embedding, serialization, cosine similarity."""

from __future__ import annotations

import math
import struct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openreview_cli.gateway.router import Gateway

from openreview_cli.gateway.models import CapabilityRequirement


def compute_embedding(
    text: str,
    gateway: Gateway,
    model_id: str = "nomic-embed-text",
) -> tuple[list[float], int]:
    """Compute embedding vector for text via AI Gateway.

    Returns:
        (vector_as_list, dimension)

    Raises:
        EmbeddingError: If the gateway call fails.
    """
    try:
        # The gateway embed method returns a list of embeddings (one per input text)
        embeddings = gateway.embed(
            "embedding",
            [text],
            requirement=CapabilityRequirement(capability="embedding"),
        )
    except Exception as exc:
        from openreview_cli.retrieval.errors import EmbeddingError

        raise EmbeddingError(f"Embedding computation failed: {exc}") from exc

    if not embeddings or not embeddings[0]:
        from openreview_cli.retrieval.errors import EmbeddingError

        raise EmbeddingError("Gateway returned empty embedding")

    vector = embeddings[0]
    dimension = len(vector)
    return vector, dimension


def serialize_embedding(vector: list[float]) -> bytes:
    """Convert float list to raw float32 bytes (little-endian)."""
    return struct.pack(f"<{len(vector)}f", *vector)


def deserialize_embedding(blob: bytes, dimension: int) -> list[float]:
    """Convert raw float32 bytes back to float list."""
    return list(struct.unpack(f"<{dimension}f", blob))


def cosine_similarity(
    query_vec: list[float],
    chunk_vec: list[float],
    query_norm: float | None = None,
    chunk_norm: float | None = None,
) -> float:
    """Compute cosine similarity between query and chunk vectors.

    If pre-computed norms are provided, skips the sqrt for each vector.
    Returns value in [-1.0, 1.0].
    """
    dot = math.fsum(a * b for a, b in zip(query_vec, chunk_vec, strict=True))
    qn = query_norm if query_norm is not None else math.sqrt(math.fsum(a * a for a in query_vec))
    cn = chunk_norm if chunk_norm is not None else math.sqrt(math.fsum(b * b for b in chunk_vec))

    if qn == 0.0 or cn == 0.0:
        return 0.0
    return dot / (qn * cn)


def compute_l2_norm(vec: list[float]) -> float:
    """Compute L2 norm of a vector."""
    return math.sqrt(math.fsum(v * v for v in vec))
