CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'document_status') THEN
    CREATE TYPE document_status AS ENUM ('uploaded', 'queued', 'processing', 'done', 'failed');
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  original_filename text NOT NULL,
  storage_url text NOT NULL,
  status document_status NOT NULL DEFAULT 'uploaded',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  error_message text
);

CREATE TABLE IF NOT EXISTS metadata_standard (
  document_id uuid PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
  core jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_metadata_standard_core_creator
  ON metadata_standard ((core->>'creator'));

CREATE INDEX IF NOT EXISTS idx_metadata_standard_core_created
  ON metadata_standard ((core->>'created'));

CREATE TABLE IF NOT EXISTS metadata_semantic (
  document_id uuid PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
  semantic jsonb NOT NULL DEFAULT '{}'::jsonb
);
