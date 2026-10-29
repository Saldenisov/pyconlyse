-- Scalar-only camera analysis. No image, base64, compressed pixel or profile columns.
CREATE TABLE IF NOT EXISTS sup_camera_state (
    camera_id text PRIMARY KEY,
    reference_revision bigint NOT NULL DEFAULT 0 CHECK (reference_revision >= 0),
    mode_revision bigint NOT NULL DEFAULT 0 CHECK (mode_revision >= 0),
    mode text NOT NULL DEFAULT 'manual' CHECK (mode IN ('manual','auto'))
);
CREATE TABLE IF NOT EXISTS sup_camera_references (
    camera_id text NOT NULL REFERENCES sup_camera_state(camera_id),
    revision bigint NOT NULL CHECK (revision > 0),
    frame_identity text NOT NULL,
    x double precision NOT NULL,
    y double precision NOT NULL,
    radius_px double precision NOT NULL CHECK (radius_px > 0),
    width integer NOT NULL CHECK (width > 0),
    height integer NOT NULL CHECK (height > 0),
    source_kind text NOT NULL,
    processing text NOT NULL,
    saved_utc timestamptz NOT NULL,
    PRIMARY KEY (camera_id,revision)
);
CREATE TABLE IF NOT EXISTS sup_camera_modes (
    camera_id text NOT NULL REFERENCES sup_camera_state(camera_id),
    revision bigint NOT NULL CHECK (revision > 0),
    mode text NOT NULL CHECK (mode IN ('manual','auto')),
    saved_utc timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (camera_id,revision)
);
CREATE TABLE IF NOT EXISTS sup_camera_observations (
    camera_id text NOT NULL,
    frame_identity text NOT NULL,
    source_session_id text NOT NULL,
    capture_session_id text NOT NULL,
    source_sequence bigint NOT NULL,
    channel bigint NOT NULL,
    width integer NOT NULL,
    height integer NOT NULL,
    observed_utc timestamptz NOT NULL,
    received_utc timestamptz NOT NULL,
    quality text NOT NULL,
    x double precision,
    y double precision,
    peak double precision NOT NULL,
    background double precision NOT NULL,
    total_intensity double precision NOT NULL,
    analysis_version text NOT NULL,
    source_kind text NOT NULL,
    processing text NOT NULL,
    source_age_seconds double precision NOT NULL,
    PRIMARY KEY (camera_id,frame_identity)
);
CREATE INDEX IF NOT EXISTS sup_camera_observations_time ON sup_camera_observations(camera_id,observed_utc);
-- An earlier development schema may lack coordinate provenance. Unknown does
-- not acquire the current source's calibration and therefore cannot auto-align.
ALTER TABLE sup_camera_references ADD COLUMN IF NOT EXISTS source_kind text NOT NULL DEFAULT 'unknown';
ALTER TABLE sup_camera_references ADD COLUMN IF NOT EXISTS processing text NOT NULL DEFAULT 'unknown';
ALTER TABLE sup_camera_observations ADD COLUMN IF NOT EXISTS source_kind text NOT NULL DEFAULT 'unknown';
ALTER TABLE sup_camera_observations ADD COLUMN IF NOT EXISTS processing text NOT NULL DEFAULT 'unknown';
ALTER TABLE sup_camera_observations ADD COLUMN IF NOT EXISTS source_age_seconds double precision;
