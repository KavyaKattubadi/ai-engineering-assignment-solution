from datetime import datetime
from typing import Optional, List
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, HttpUrl, field_validator
import secrets


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class AgentRegisterRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    industry_category: str = Field(..., min_length=1, max_length=100)
    webhook_url: str
    interest_manifesto: str = Field(..., min_length=10, max_length=4000)

    @field_validator("webhook_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("webhook_url must start with http:// or https://")
        return v


class AgentResponse(BaseModel):
    id: UUID
    company_name: str
    industry_category: str
    webhook_url: str
    interest_manifesto: str
    trust_score: float
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PostCreateRequest(BaseModel):
    author_agent_id: UUID
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1, max_length=10000)
    expires_at: Optional[datetime] = None


class PostResponse(BaseModel):
    id: UUID
    author_agent_id: UUID
    title: str
    content: str
    created_at: datetime
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CommentCreateRequest(BaseModel):
    author_agent_id: UUID
    content: str = Field(..., min_length=1, max_length=5000)


class CommentResponse(BaseModel):
    id: UUID
    post_id: UUID
    author_agent_id: UUID
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class RoutingResult(BaseModel):
    target_agent_id: UUID
    company_name: str
    vector_score: float
    rerank_score: float
    notified: bool


class PostWithRoutingResponse(BaseModel):
    post: PostResponse
    notified_agents: List[RoutingResult]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def generate_webhook_secret() -> str:
    return secrets.token_urlsafe(32)