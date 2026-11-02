"""Hybrid Search (Dense Semantic + Lexical BM25 Scoring) and Reranking."""
import math
import re
from typing import List, Dict, Any, Optional
from collections import Counter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Document, DocumentChunk
from app.retrieval.embeddings import get_embedding_provider


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def compute_bm25_lexical_score(query: str, text: str, avg_doc_len: float = 80.0, k1: float = 1.5, b: float = 0.75) -> float:
    """
    Computes BM25-based lexical relevance score between query terms and text document.
    """
    q_tokens = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 2]
    doc_tokens = re.findall(r"\w+", text.lower())
    if not q_tokens or not doc_tokens:
        return 0.0

    doc_len = len(doc_tokens)
    doc_freqs = Counter(doc_tokens)
    score = 0.0

    for token in q_tokens:
        tf = doc_freqs.get(token, 0)
        if tf > 0:
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * (doc_len / max(1.0, avg_doc_len)))
            score += numerator / max(0.001, denominator)

    return score / max(1.0, len(q_tokens))


def reciprocal_rank_fusion(dense_score: float, lexical_score: float, alpha: float = 0.6) -> float:
    """
    Blends dense vector similarity and lexical BM25 matching into a unified hybrid score.
    """
    # Normalize lexical score into [0, 1] range using sigmoid-like scaling
    norm_lexical = min(1.0, lexical_score / 2.0)
    return round((alpha * dense_score) + ((1.0 - alpha) * norm_lexical), 4)


async def search_document_chunks(
    db: AsyncSession,
    user_id: str,
    query: str,
    top_k: int = 5,
    threshold: float = 0.35,
    document_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Searches indexed document chunks for the given user, computing hybrid (Dense + BM25) similarity.
    Enforces strict user isolation.
    """
    embedding_provider = get_embedding_provider()
    query_vector = await embedding_provider.embed_query(query)

    # Fetch candidate chunks belonging to the user
    stmt = (
        select(DocumentChunk, Document.filename)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(Document.user_id == user_id, Document.status == "ready")
    )
    if document_id:
        stmt = stmt.where(Document.id == document_id)

    result = await db.execute(stmt)
    rows = result.all()

    scored_chunks: List[Dict[str, Any]] = []
    for chunk, filename in rows:
        if not chunk.embedding:
            continue
        dense_sim = cosine_similarity(query_vector, chunk.embedding)
        lexical_sim = compute_bm25_lexical_score(query, chunk.content)
        hybrid_score = reciprocal_rank_fusion(dense_sim, lexical_sim, alpha=0.65)

        if hybrid_score >= threshold or dense_sim >= threshold:
            scored_chunks.append({
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "filename": filename,
                "content": chunk.content,
                "metadata": chunk.metadata_json or {},
                "score": hybrid_score,
                "dense_score": round(dense_sim, 4),
                "lexical_score": round(lexical_sim, 4),
                "source_type": "document"
            })

    # Sort descending by hybrid similarity score
    scored_chunks.sort(key=lambda x: x["score"], reverse=True)
    return scored_chunks[:top_k]
