-- ─────────────────────────────────────────────────────────────────────────────
-- Character Engine — Core Migrations
-- Run this in Supabase SQL Editor
-- ─────────────────────────────────────────────────────────────────────────────

-- Enable pgvector extension for memory embeddings
CREATE EXTENSION IF NOT EXISTS vector;


-- ─── CHARACTERS ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS characters (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT NOT NULL,
    tagline             TEXT,
    base_card           JSONB NOT NULL DEFAULT '{}',
    current_state       JSONB NOT NULL DEFAULT '{}',
    display_profile     JSONB NOT NULL DEFAULT '{}',
    preferred_model     TEXT DEFAULT 'claude-sonnet-4-6',
    is_demo             BOOLEAN DEFAULT FALSE,
    total_chats         INT DEFAULT 0,
    total_messages      INT DEFAULT 0,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);


-- ─── CONVERSATIONS ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    character_id    UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    session_id      UUID NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    model_used      TEXT,
    tokens_used     INT DEFAULT 0,
    processed       BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_character_id ON conversations(character_id);
CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_processed ON conversations(processed);


-- ─── MEMORIES ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS memories (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    character_id        UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    content             TEXT NOT NULL,
    embedding           VECTOR(1536),
    importance          INT DEFAULT 5 CHECK (importance BETWEEN 1 AND 10),
    tier                TEXT DEFAULT 'active' CHECK (tier IN ('active', 'compressed', 'archived')),
    locked              BOOLEAN DEFAULT FALSE,
    retrieval_count     INT DEFAULT 0,
    source_ids          UUID[] DEFAULT '{}',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    last_accessed       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memories_character_id ON memories(character_id);
CREATE INDEX IF NOT EXISTS idx_memories_tier ON memories(tier);
CREATE INDEX IF NOT EXISTS idx_memories_locked ON memories(locked);
-- Vector similarity search index
CREATE INDEX IF NOT EXISTS idx_memories_embedding
    ON memories USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);


-- ─── CHARACTER STATE LOG ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS character_state_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    character_id    UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    field           TEXT NOT NULL,
    old_value       TEXT,
    new_value       TEXT,
    triggered_by    UUID REFERENCES conversations(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_state_log_character_id ON character_state_log(character_id);


-- ─── CONFIG ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS config (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key         TEXT UNIQUE NOT NULL,
    value       TEXT NOT NULL,
    is_secret   BOOLEAN DEFAULT FALSE,
    description TEXT,
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Seed default config values
INSERT INTO config (key, value, description) VALUES
    ('claude_model',                    'claude-sonnet-4-6',        'Claude model used for chat and extraction'),
    ('embedding_model',                 'text-embedding-3-small',   'OpenAI model for memory embeddings'),
    ('extraction_threshold',            '20',                       'Messages before auto memory extraction'),
    ('memory_injection_limit',          '6',                        'Max memories injected per request'),
    ('retrieval_similarity_weight',     '0.6',                      'Weight for semantic similarity in re-ranking'),
    ('retrieval_importance_weight',     '0.3',                      'Weight for importance in re-ranking'),
    ('retrieval_recency_weight',        '0.1',                      'Weight for recency in re-ranking'),
    ('compression_low_days',            '7',                        'Days before low-importance memories compress'),
    ('compression_mid_days',            '30',                       'Days before mid-importance memories compress'),
    ('recent_messages_limit',           '15',                       'Recent messages included per request'),
    ('session_timeout_hours',           '2',                        'Hours of inactivity before new session'),
    ('default_character_greeting',      'true',                     'Whether characters start with a greeting')
ON CONFLICT (key) DO NOTHING;


-- ─── ALLOWED USERS ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS allowed_users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       TEXT UNIQUE NOT NULL,
    role        TEXT DEFAULT 'owner',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);


-- ─── DEMO CODES ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS demo_codes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code                TEXT UNIQUE NOT NULL,
    label               TEXT,
    total_token_budget  INT NOT NULL DEFAULT 10000,
    tokens_used         INT DEFAULT 0,
    max_activations     INT DEFAULT 1,
    activations_used    INT DEFAULT 0,
    notify_on_use       BOOLEAN DEFAULT TRUE,
    expires_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);


-- ─── DEMO SESSIONS ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS demo_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code_id         UUID NOT NULL REFERENCES demo_codes(id) ON DELETE CASCADE,
    session_token   TEXT UNIQUE NOT NULL,
    character_id    UUID REFERENCES characters(id) ON DELETE SET NULL,
    tokens_used     INT DEFAULT 0,
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    last_active     TIMESTAMPTZ DEFAULT NOW(),
    ended           BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_demo_sessions_token ON demo_sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_demo_sessions_code_id ON demo_sessions(code_id);


-- ─── SHARED REPLAYS ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS shared_replays (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    share_id            TEXT UNIQUE NOT NULL,
    character_id        UUID REFERENCES characters(id) ON DELETE SET NULL,
    character_name      TEXT NOT NULL,
    character_avatar    TEXT,
    messages            JSONB NOT NULL DEFAULT '[]',
    view_count          INT DEFAULT 0,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_shared_replays_share_id ON shared_replays(share_id);


-- ─── UPDATED_AT TRIGGER ──────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_characters_updated_at
    BEFORE UPDATE ON characters
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_config_updated_at
    BEFORE UPDATE ON config
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- ─── MEMORY SIMILARITY SEARCH FUNCTION ───────────────────────────────────────
CREATE OR REPLACE FUNCTION search_memories(
    p_character_id  UUID,
    p_embedding     VECTOR(1536),
    p_limit         INT DEFAULT 10,
    p_tier_exclude  TEXT DEFAULT 'archived'
)
RETURNS TABLE (
    id              UUID,
    content         TEXT,
    importance      INT,
    tier            TEXT,
    locked          BOOLEAN,
    retrieval_count INT,
    last_accessed   TIMESTAMPTZ,
    similarity      FLOAT
)
LANGUAGE SQL
AS $$
    SELECT
        m.id,
        m.content,
        m.importance,
        m.tier,
        m.locked,
        m.retrieval_count,
        m.last_accessed,
        1 - (m.embedding <=> p_embedding) AS similarity
    FROM memories m
    WHERE
        m.character_id = p_character_id
        AND m.tier != p_tier_exclude
        AND m.embedding IS NOT NULL
    ORDER BY m.embedding <=> p_embedding
    LIMIT p_limit;
$$;
