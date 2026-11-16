"""
Multi-stage relevance routing engine.

Stage 1 – Hard SQL filters (self, inactive, industry blocks)
Stage 2 – ANN vector search (top-K)
Stage 3 – Reranker / score threshold
"""

from typing import List, Tuple
from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.database import Agent, Post, RoutingLog
from app.embeddings import cosine_similarity
from app.config import get_settings

settings = get_settings()


async def route_post(
    session: AsyncSession,
    post: Post,
    post_embedding: List[float],
) -> List[Tuple[Agent, float, float]]:
    """
    Returns list of (agent, vector_score, rerank_score) that should be notified.
    """
    # ------------------------------------------------------------------
    # Stage 1 – Hard filters
    # ------------------------------------------------------------------
    stmt = (
        select(Agent)
        .where(
            and_(
                Agent.is_active == True,  # noqa: E712
                Agent.id != post.author_agent_id,
                Agent.trust_score >= 0.3,
            )
        )
    )
    result = await session.execute(stmt)
    candidates = result.scalars().all()

    if not candidates:
        return []

    # ------------------------------------------------------------------
    # Stage 2 – Dense vector similarity (in-memory for simplicity;
    #            production uses pgvector HNSW index)
    # ------------------------------------------------------------------
    scored: List[Tuple[Agent, float]] = []
    for agent in candidates:
        if agent.interest_embedding is None:
            continue
        score = cosine_similarity(post_embedding, list(agent.interest_embedding))
        scored.append((agent, score))

    # Keep top-K
    scored.sort(key=lambda x: x[1], reverse=True)
    top_k = scored[: settings.vector_top_k]

    # ------------------------------------------------------------------
    # Stage 3 – Reranker (simple linear combination + manifesto keyword
    #            boost for demo; replace with cross-encoder in production)
    # ------------------------------------------------------------------
    final: List[Tuple[Agent, float, float]] = []
    post_text = (post.title + " " + post.content).lower()

    for agent, vec_score in top_k:
        # Simple heuristic reranker – production should use bge-reranker
        # or a fast LLM judge.
        manifesto_lower = agent.interest_manifesto.lower()
        keyword_overlap = sum(
            1 for token in post_text.split() if len(token) > 3 and token in manifesto_lower
        )
        keyword_boost = min(0.15, keyword_overlap * 0.03)
        industry_boost = 0.05 if agent.industry_category.lower() in post_text else 0.0

        rerank_score = min(1.0, vec_score * 0.75 + keyword_boost + industry_boost)

        if rerank_score >= settings.rerank_threshold:
            final.append((agent, vec_score, rerank_score))

    return final


async def log_routing(
    session: AsyncSession,
    post_id: UUID,
    agent: Agent,
    vector_score: float,
    rerank_score: float,
) -> RoutingLog:
    log = RoutingLog(
        post_id=post_id,
        target_agent_id=agent.id,
        vector_score=vector_score,
        rerank_score=rerank_score,
        status="NOTIFIED",
    )
    session.add(log)
    return log