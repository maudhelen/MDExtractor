# Extractor

Minimal steps to extract DOCX core metadata into Postgres.

## Prereqs

- Docker Desktop running
- Python 3.11+
- uv installed

## Start Postgres

From repo root (this project already has `pyproject.toml`/`uv.lock`, so `uv init` is not required):

```bash
docker compose -f infra/docker-compose.yaml up -d
```

## Configure DB URL

Create a `.env` file at repo root:

```bash
DATABASE_URL=postgresql://mdx:mdx_password@localhost:5432/mdextractor
```

## Install Python deps (uv)

From repo root:

```bash
cd services/extractor
uv venv
uv sync
```

## Run extraction

Your test files are in `data/` at repo root:

```bash
uv run python services/extractor/src/extract_metadata.py --input data
```

For a single file:

```bash
uv run python services/extractor/src/extract_metadata.py --input data/example.docx
```

## Verify in DB

```bash
psql postgresql://mdx:mdx_password@localhost:5432/mdextractor -c "\\dx" -c "\\dt" -c "select id, original_filename, status from documents order by created_at desc limit 5;"
```
