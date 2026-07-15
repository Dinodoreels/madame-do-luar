-- Fase 8 - CRM Inteligente
-- Execute no SQL Editor do Supabase caso as tabelas ainda nao existam.

CREATE TABLE IF NOT EXISTS customer_tags (
    tag_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    color TEXT,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_customer_tags (
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    tag_id UUID REFERENCES customer_tags(tag_id) ON DELETE CASCADE,
    assigned_by_user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (user_id, tag_id)
);

CREATE TABLE IF NOT EXISTS customer_segments (
    segment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    rules JSONB DEFAULT '{}'::jsonb,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_customer_segments (
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    segment_id UUID REFERENCES customer_segments(segment_id) ON DELETE CASCADE,
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (user_id, segment_id)
);

CREATE TABLE IF NOT EXISTS admin_customer_notes (
    note_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    admin_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    note TEXT NOT NULL,
    visibility TEXT DEFAULT 'internal' CHECK (visibility IN ('internal', 'support', 'sales', 'marketing')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS segment_automation_triggers (
    trigger_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    segment_id UUID REFERENCES customer_segments(segment_id) ON DELETE CASCADE,
    rule_id UUID REFERENCES automation_rules(rule_id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    event_type TEXT DEFAULT 'segment_entry',
    channel TEXT CHECK (channel IN ('email', 'whatsapp')),
    template TEXT,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_customer_tags_status ON customer_tags(status);
CREATE INDEX IF NOT EXISTS idx_customer_segments_status ON customer_segments(status);
CREATE INDEX IF NOT EXISTS idx_admin_customer_notes_user_id ON admin_customer_notes(user_id);
CREATE INDEX IF NOT EXISTS idx_admin_customer_notes_created_at ON admin_customer_notes(created_at);
CREATE INDEX IF NOT EXISTS idx_segment_automation_triggers_segment_id ON segment_automation_triggers(segment_id);
CREATE INDEX IF NOT EXISTS idx_segment_automation_triggers_status ON segment_automation_triggers(status);
