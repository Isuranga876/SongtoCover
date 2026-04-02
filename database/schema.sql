-- schema.sql
-- Supabase Schema for Song2Cover

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table: songs
CREATE TABLE songs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID DEFAULT auth.uid(), -- References Supabase auth system, can be null for anonymous
    original_filename TEXT NOT NULL,
    stored_file_path TEXT,
    upload_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    duration_seconds FLOAT,
    file_type TEXT,
    bpm FLOAT,
    musical_key TEXT,
    analysis_status TEXT DEFAULT 'pending', -- 'pending', 'analyzing', 'completed', 'failed'
    arrangement_status TEXT DEFAULT 'pending', -- 'pending', 'arranged', 'failed'
    selected_style_preset TEXT,
    notes TEXT
);

-- Table: sections
CREATE TABLE sections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    song_id UUID REFERENCES songs(id) ON DELETE CASCADE,
    start_time FLOAT NOT NULL,
    end_time FLOAT NOT NULL,
    section_label TEXT NOT NULL, -- 'intro', 'vocal', 'interlude', 'outro'
    confidence_score FLOAT,
    rule_source TEXT,
    vocal_activity_state BOOLEAN
);

-- RLS (Row Level Security) - optional but recommended for actual app
ALTER TABLE songs ENABLE ROW LEVEL SECURITY;
ALTER TABLE sections ENABLE ROW LEVEL SECURITY;

-- If allowing anonymous MVP uploads:
CREATE POLICY "Allow public inserts" ON songs FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow public viewing" ON songs FOR SELECT USING (true);

CREATE POLICY "Allow public inserts" ON sections FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow public viewing" ON sections FOR SELECT USING (true);
