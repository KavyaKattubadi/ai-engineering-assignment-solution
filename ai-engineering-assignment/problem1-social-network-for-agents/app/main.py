"""
FastAPI application – Social Network for AI Agents
"""

from contextlib import asynccontextmanager
from typing import List
from uuid import UUID
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db, Agent, Post, Comment, RoutingLog, engine, Base
from app.models import (
    AgentRegisterRequest,
    AgentResponse,
    PostCreateRequest,
    PostResponse,
    CommentCreateRequest,
    CommentResponse,
    RoutingResult,
    PostWithRoutingResponse,
    generate_webhook_secret,
)
from app.embeddings import get_embedding
from app.routing import route_post, log_routing
from app.webhooks import deliver_notification


@asynccontextmanager
async def lifespan(app: FastAPI):
    # On startup – create tables if they do not exist (dev convenience)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="AI Agents Social Network",
    description="Platform for AI agents to post and discover relevant cross-company opportunities.",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

@app.post("/api/v1/agents/register", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def register_agent(
    body: AgentRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    embedding = await get_embedding(body.interest_manifesto)
    secret = generate_webhook_secret()

    agent = Agent(
        company_name=body.company_name,
        industry_category=body.industry_category,
        webhook_url=body.webhook_url,
        interest_manifesto=body.interest_manifesto,
        interest_embedding=embedding,
        webhook_secret=secret,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


@app.get("/api/v1/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


# ---------------------------------------------------------------------------
# Posts + Routing
# ---------------------------------------------------------------------------

@app.post("/api/v1/posts", response_model=PostWithRoutingResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    body: PostCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    # Validate author exists
    result = await db.execute(select(Agent).where(Agent.id == body.author_agent_id))
    author = result.scalar_one_or_none()
    if not author:
        raise HTTPException(status_code=404, detail="Author agent not found")

    # Embed post
    text_to_embed = f"{body.title}\n{body.content}"
    embedding = await get_embedding(text_to_embed)

    post = Post(
        author_agent_id=body.author_agent_id,
        title=body.title,
        content=body.content,
        post_embedding=embedding,
        expires_at=body.expires_at,
    )
    db.add(post)
    await db.flush()  # get post.id

    # Multi-stage routing
    matched = await route_post(db, post, embedding)

    notified: List[RoutingResult] = []
    for agent, vec_score, rerank_score in matched:
        await log_routing(db, post.id, agent, vec_score, rerank_score)

        # Fire-and-forget style delivery (in production push to Celery/Redis)
        success = await deliver_notification(
            webhook_url=agent.webhook_url,
            secret=agent.webhook_secret,
            post_id=post.id,
            title=post.title,
            content=post.content,
            author_company=author.company_name,
        )
        if not success:
            # mark as FAILED in a real system
            pass

        notified.append(
            RoutingResult(
                target_agent_id=agent.id,
                company_name=agent.company_name,
                vector_score=round(vec_score, 4),
                rerank_score=round(rerank_score, 4),
                notified=True,
            )
        )

    await db.commit()
    await db.refresh(post)

    return PostWithRoutingResponse(
        post=PostResponse.model_validate(post),
        notified_agents=notified,
    )


@app.get("/api/v1/posts/{post_id}", response_model=PostResponse)
async def get_post(post_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


# ---------------------------------------------------------------------------
# Comments (agent responses)
# ---------------------------------------------------------------------------

@app.post(
    "/api/v1/posts/{post_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    post_id: UUID,
    body: CommentCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    # Validate post & agent
    post_result = await db.execute(select(Post).where(Post.id == post_id))
    post = post_result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    agent_result = await db.execute(select(Agent).where(Agent.id == body.author_agent_id))
    agent = agent_result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    comment = Comment(
        post_id=post_id,
        author_agent_id=body.author_agent_id,
        content=body.content,
    )
    db.add(comment)

    # Mark corresponding routing log as ENGAGED (feedback signal)
    log_result = await db.execute(
        select(RoutingLog).where(
            RoutingLog.post_id == post_id,
            RoutingLog.target_agent_id == body.author_agent_id,
        )
    )
    log = log_result.scalar_one_or_none()
    if log:
        log.status = "ENGAGED"
        from datetime import datetime, timezone
        log.engaged_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(comment)
    return comment


@app.get("/api/v1/posts/{post_id}/comments", response_model=List[CommentResponse])
async def list_comments(post_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Comment).where(Comment.post_id == post_id).order_by(Comment.created_at)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}