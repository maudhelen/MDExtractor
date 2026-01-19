from __future__ import annotations

from contextlib import asynccontextmanager

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal

import asyncpg
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

DocumentStatus = Literal["uploaded", "queued", "processing", "done", "failed"]

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://mdx:mdx_password@localhost:5432/mdextractor",
)

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./data/uploads"))

class DocumentOut(BaseModel):
    id: uuid.UUID
    original_filename: str
    storage_url: str
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime
    error_message: str | None

class DocumentDetail(DocumentOut):
    core: dict = Field(default_factory=dict)
    # semantic: dict = Field(default_factory=dict)

class DocumentList(BaseModel):
    items: list[DocumentOut]
    limit: int
    offset: int

@asynccontextmanager
async def lifespan(app: FastAPI):
    async def init_connection(conn: asyncpg.Connection) -> None:
        await conn.set_type_codec(
            "jsonb",
            encoder=json.dumps,
            decoder=json.loads,
            schema="pg_catalog",
        )
        await conn.set_type_codec(
            "json",
            encoder=json.dumps,
            decoder=json.loads,
            schema="pg_catalog",
        )

    pool = await asyncpg.create_pool(DATABASE_URL, init=init_connection)
    app.state.pool = pool
    try:
        yield
    finally:
        await pool.close()

app = FastAPI(title="MDExtractor API", lifespan=lifespan)

def row_to_document(row: asyncpg.Record) -> DocumentOut:
    return DocumentOut(
        id=row["id"],
        original_filename=row["original_filename"],
        storage_url=row["storage_url"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        error_message=row["error_message"],
    )

@app.post("/documents", response_model=DocumentOut, status_code=201)
async def upload_document(file: UploadFile = File(...)) -> DocumentOut:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename.")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename).suffix
    document_id = uuid.uuid4()
    storage_path = UPLOAD_DIR / f"{document_id}{suffix}"

    try:
        with storage_path.open("wb") as handle:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc

    pool: asyncpg.Pool = app.state.pool
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO documents (id, original_filename, storage_url, status)
                VALUES ($1, $2, $3, 'uploaded')
                RETURNING id, original_filename, storage_url, status, created_at, updated_at, error_message
                """,
                document_id,
                file.filename,
                str(storage_path),
            )
    except Exception as exc:
        if storage_path.exists():
            storage_path.unlink()
        raise HTTPException(status_code=500, detail=f"Database insert failed: {exc}") from exc

    if row is None:
        raise HTTPException(status_code=500, detail="Upload failed to persist.")

    return row_to_document(row)

@app.get("/documents", response_model=DocumentList)
async def list_documents(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> DocumentList:
    pool: asyncpg.Pool = app.state.pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, original_filename, storage_url, status, created_at, updated_at, error_message
            FROM documents
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
    return DocumentList(items=[row_to_document(row) for row in rows], limit=limit, offset=offset)

@app.get("/documents/{document_id}", response_model=DocumentDetail)
async def get_document(document_id: uuid.UUID) -> DocumentDetail:
    pool: asyncpg.Pool = app.state.pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
              d.id,
              d.original_filename,
              d.storage_url,
              d.status,
              d.created_at,
              d.updated_at,
              d.error_message,
              COALESCE(ms.core, '{}'::jsonb) AS core
            FROM documents d
            LEFT JOIN metadata_standard AS ms ON ms.document_id = d.id
            WHERE d.id = $1
            """,
            document_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    return DocumentDetail(
        id=row["id"],
        original_filename=row["original_filename"],
        storage_url=row["storage_url"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        error_message=row["error_message"],
        core=row["core"],
    )
