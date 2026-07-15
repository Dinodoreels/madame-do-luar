-- Fase 8 - Analytics e produto
-- Registra eventos de funil, conversao, abandono, retencao e uso real.

CREATE TABLE IF NOT EXISTS analytics_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_name TEXT NOT NULL,
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    admin_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    session_id TEXT,
    anonymous_id TEXT,
    page_url TEXT,
    referrer TEXT,
    source TEXT DEFAULT 'frontend',
    entity_type TEXT,
    entity_id TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analytics_events_name_created_at
    ON analytics_events(event_name, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_analytics_events_user_created_at
    ON analytics_events(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_analytics_events_session_created_at
    ON analytics_events(session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_analytics_events_entity
    ON analytics_events(entity_type, entity_id);

CREATE INDEX IF NOT EXISTS idx_analytics_events_metadata_gin
    ON analytics_events USING GIN (metadata);

-- Views de leitura rapida para painel/admin.
CREATE OR REPLACE VIEW analytics_event_daily AS
SELECT
    date_trunc('day', created_at)::date AS day,
    event_name,
    COUNT(*) AS events,
    COUNT(DISTINCT COALESCE(user_id::text, anonymous_id, session_id)) AS unique_actors
FROM analytics_events
GROUP BY 1, 2;

CREATE OR REPLACE VIEW analytics_funnel_30d AS
SELECT
    event_name,
    COUNT(*) AS events,
    COUNT(DISTINCT COALESCE(user_id::text, anonymous_id, session_id)) AS unique_actors
FROM analytics_events
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY event_name;
