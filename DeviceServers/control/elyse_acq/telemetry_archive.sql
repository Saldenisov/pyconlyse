CREATE TABLE IF NOT EXISTS acq_archive_frames (
    uid text PRIMARY KEY,
    observed_utc timestamptz NOT NULL,
    kind text NOT NULL,
    provenance text NOT NULL,
    digest text NOT NULL,
    payload_zlib bytea NOT NULL,
    receiver_session text,
    receiver_count bigint,
    inserted_utc timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS acq_archive_frames_time ON acq_archive_frames(observed_utc, uid);
CREATE TABLE IF NOT EXISTS acq_archive_types (
    digest text PRIMARY KEY,
    definition jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS acq_archive_banks (
    frame_uid text NOT NULL REFERENCES acq_archive_frames(uid),
    bank text NOT NULL,
    observed_utc timestamptz NOT NULL,
    data jsonb,
    error jsonb NOT NULL,
    stale boolean NOT NULL,
    age_seconds double precision,
    source_session text,
    source_sequence numeric,
    source_seconds_1904 numeric,
    producer_kind text,
    type_digest text REFERENCES acq_archive_types(digest),
    PRIMARY KEY(frame_uid, bank)
);
CREATE INDEX IF NOT EXISTS acq_archive_banks_time ON acq_archive_banks(bank, observed_utc, frame_uid);
CREATE TABLE IF NOT EXISTS acq_archive_imports (
    archive_id text PRIMARY KEY,
    source_path text NOT NULL,
    committed_rows bigint NOT NULL,
    imported_rows bigint NOT NULL DEFAULT 0,
    state text NOT NULL,
    updated_utc timestamptz NOT NULL DEFAULT clock_timestamp()
);
