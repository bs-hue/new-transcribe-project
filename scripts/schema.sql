-- PostgreSQL schema for the Content Research Hub.
--
-- GENERATED FILE — do not edit by hand. It is produced from the SQLAlchemy
-- models, so it cannot drift from what the application expects:
--
--   docker compose -f docker-compose.supabase.yml --env-file .env.production \
--     run --rm api python -m alembic upgrade head --sql > scripts/schema.sql
--
-- You normally do NOT need this file. `python -m app.cli migrate` applies the
-- same thing over a connection, and keeps working for every future schema
-- change. This exists for the case where you would rather paste SQL into the
-- Supabase SQL Editor and watch it happen.
--
-- The final INSERT into alembic_version is not optional: it records which
-- migration this schema represents. Without it, the next `migrate` would try to
-- create these tables a second time and fail. With it, `migrate` correctly
-- reports "up to date" and future migrations apply cleanly on top.

BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> fc77b2bb710f

CREATE TABLE app_settings (
    key VARCHAR(64) NOT NULL, 
    value TEXT NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_by VARCHAR(32), 
    PRIMARY KEY (key)
);

CREATE TABLE users (
    id VARCHAR(32) NOT NULL, 
    email VARCHAR(255) NOT NULL, 
    full_name VARCHAR(255), 
    hashed_password VARCHAR(128) NOT NULL, 
    role VARCHAR(16) NOT NULL, 
    is_active BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    last_login_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE TABLE videos (
    id VARCHAR(32) NOT NULL, 
    platform VARCHAR(32) NOT NULL, 
    platform_video_id VARCHAR(128) NOT NULL, 
    source_url TEXT NOT NULL, 
    canonical_url TEXT NOT NULL, 
    title TEXT, 
    description TEXT, 
    author VARCHAR(255), 
    author_url TEXT, 
    thumbnail_url TEXT, 
    duration_seconds FLOAT, 
    estimated_size_bytes INTEGER, 
    view_count INTEGER, 
    like_count INTEGER, 
    published_at TIMESTAMP WITH TIME ZONE, 
    raw_metadata JSON, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_video_platform_id UNIQUE (platform, platform_video_id)
);

CREATE INDEX ix_videos_author ON videos (author);

CREATE INDEX ix_videos_created_at ON videos (created_at);

CREATE INDEX ix_videos_platform ON videos (platform);

CREATE TABLE jobs (
    id VARCHAR(32) NOT NULL, 
    video_id VARCHAR(32) NOT NULL, 
    batch_id VARCHAR(32), 
    submitted_by VARCHAR(32), 
    status VARCHAR(16) NOT NULL, 
    stage VARCHAR(32) NOT NULL, 
    progress FLOAT NOT NULL, 
    attempts INTEGER NOT NULL, 
    error_code VARCHAR(64), 
    error_message TEXT, 
    language VARCHAR(16), 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    started_at TIMESTAMP WITH TIME ZONE, 
    finished_at TIMESTAMP WITH TIME ZONE, 
    heartbeat_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(submitted_by) REFERENCES users (id) ON DELETE SET NULL, 
    FOREIGN KEY(video_id) REFERENCES videos (id) ON DELETE CASCADE
);

CREATE INDEX ix_jobs_batch_id ON jobs (batch_id);

CREATE INDEX ix_jobs_status ON jobs (status);

CREATE INDEX ix_jobs_status_created ON jobs (status, created_at);

CREATE INDEX ix_jobs_submitted_by ON jobs (submitted_by);

CREATE INDEX ix_jobs_video_id ON jobs (video_id);

CREATE TABLE transcripts (
    id VARCHAR(32) NOT NULL, 
    video_id VARCHAR(32) NOT NULL, 
    job_id VARCHAR(32), 
    text TEXT NOT NULL, 
    language VARCHAR(16), 
    provider VARCHAR(32) NOT NULL, 
    model VARCHAR(64), 
    word_count INTEGER NOT NULL, 
    duration_seconds FLOAT, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(video_id) REFERENCES videos (id) ON DELETE CASCADE
);

CREATE INDEX ix_transcripts_video_created ON transcripts (video_id, created_at);

CREATE INDEX ix_transcripts_video_id ON transcripts (video_id);

CREATE TABLE transcript_segments (
    id VARCHAR(32) NOT NULL, 
    transcript_id VARCHAR(32) NOT NULL, 
    index INTEGER NOT NULL, 
    start FLOAT NOT NULL, 
    "end" FLOAT NOT NULL, 
    text TEXT NOT NULL, 
    speaker VARCHAR(64), 
    PRIMARY KEY (id), 
    FOREIGN KEY(transcript_id) REFERENCES transcripts (id) ON DELETE CASCADE
);

CREATE INDEX ix_segments_transcript_index ON transcript_segments (transcript_id, index);

CREATE INDEX ix_transcript_segments_transcript_id ON transcript_segments (transcript_id);

INSERT INTO alembic_version (version_num) VALUES ('fc77b2bb710f') RETURNING alembic_version.version_num;

COMMIT;

