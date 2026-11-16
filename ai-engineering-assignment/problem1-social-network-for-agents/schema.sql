-- Schema for AI Agents Social Network
-- Requires PostgreSQL 15+ with pgvector extension

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- Agents
-- ============================================================
CREATE TABLE agents (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_name        VARCHAR(255) NOT NULL,
    industry_category   VARCHAR(100) NOT NULL,
    webhook_url         TEXT NOT NULL,
    interest_manifesto  TEXT NOT NULL,
    interest_embedding  vector(1536),          -- text-embedding-3-small dimension
    trust_score         FLOAT NOT NULL DEFAULT 1.0 CHECK (trust_score >= 0 AND trust_score <= 1),
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    webhook_secret      TEXT NOT NULL,         -- for HMAC signing
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agents_industry ON agents(industry_category);
CREATE INDEX idx_agents_active ON agents(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_agents_embedding ON agents USING hnsw (interest_embedding vector_cosine_ops);

-- ============================================================
-- Posts
-- ============================================================
CREATE TABLE posts (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    author_agent_id     UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    title               VARCHAR(255) NOT NULL,
    content             TEXT NOT NULL,
    post_embedding      vector(1536),
    expires_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_posts_author ON posts(author_agent_id);
CREATE INDEX idx_posts_created ON posts(created_at DESC);
CREATE INDEX idx_posts_embedding ON posts USING hnsw (post_embedding vector_cosine_ops);

-- ============================================================
-- Comments (agent responses)
-- ============================================================
CREATE TABLE comments (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    post_id             UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    author_agent_id     UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    content             TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_comments_post ON comments(post_id);
CREATE INDEX idx_comments_author ON comments(author_agent_id);

-- ============================================================
-- Routing Logs (drives feedback & metrics)
-- ============================================================
CREATE TABLE routing_logs (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    post_id             UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    target_agent_id     UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    vector_score        FLOAT NOT NULL,        -- Stage 2 cosine similarity
    rerank_score        FLOAT NOT NULL,        -- Stage 3 final score
    status              VARCHAR(50) NOT NULL DEFAULT 'NOTIFIED'
                        CHECK (status IN ('NOTIFIED', 'ENGAGED', 'IGNORED', 'FAILED')),
    notified_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    engaged_at          TIMESTAMPTZ
);

CREATE INDEX idx_routing_post ON routing_logs(post_id);
CREATE INDEX idx_routing_target ON routing_logs(target_agent_id);
CREATE INDEX idx_routing_status ON routing_logs(status);

-- ============================================================
-- Optional: industry block lists / mutual exclusions
-- ============================================================
CREATE TABLE industry_blocks (
    source_industry     VARCHAR(100) NOT NULL,
    blocked_industry    VARCHAR(100) NOT NULL,
    PRIMARY KEY (source_industry, blocked_industry)
);

-- Example: prevent pure auto manufacturers from seeing pure food-delivery offers
-- INSERT INTO industry_blocks VALUES ('Automobile', 'Food Delivery');