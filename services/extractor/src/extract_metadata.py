import argparse
import datetime as dt
import os
from pathlib import Path

from docx import Document
from dotenv import load_dotenv
import psycopg
from psycopg.types.json import Json

CORE_FIELDS = [
    "author",
    "title",
    "subject",
    "category",
    "comments",
    "content_status",
    "created",
    "identifier",
    "keywords",
    "language",
    "last_modified_by",
    "last_printed",
    "modified",
    "revision",
    "version",
]

def serialize_core(core_props: object) -> dict:
    data = {}
    for field in CORE_FIELDS:
        value = getattr(core_props, field, None)
        if isinstance(value, (dt.datetime, dt.date)):
            data[field] = value.isoformat()
        else:
            data[field] = value
    return data


def iter_docx_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted(p for p in input_path.rglob("*.docx") if p.is_file())


def ensure_db_url(db_url: str | None) -> str:
    if db_url:
        return db_url
    env_url = os.getenv("DATABASE_URL")
    if not env_url:
        raise SystemExit("DATABASE_URL is not set. Provide --db-url or set it in .env.")
    return env_url


def insert_document(cur, file_path: Path) -> str:
    cur.execute(
        """
        INSERT INTO documents (original_filename, storage_url, status)
        VALUES (%s, %s, 'processing')
        RETURNING id
        """,
        (file_path.name, str(file_path)),
    )
    return cur.fetchone()[0]


def mark_document(cur, doc_id: str, status: str, error_message: str | None = None) -> None:
    cur.execute(
        """
        UPDATE documents
        SET status = %s,
            error_message = %s,
            updated_at = now()
        WHERE id = %s
        """,
        (status, error_message, doc_id),
    )


def insert_metadata(cur, doc_id: str, core: dict) -> None:
    cur.execute(
        """
        INSERT INTO metadata_standard (document_id, core)
        VALUES (%s, %s)
        """,
        (doc_id, Json(core)),
    )


def process_file(conn, file_path: Path) -> None:
    with conn.cursor() as cur:
        doc_id = insert_document(cur, file_path)
        conn.commit()

    try:
        doc = Document(file_path)
        core = serialize_core(doc.core_properties)

        with conn.cursor() as cur:
            insert_metadata(cur, doc_id, core)
            mark_document(cur, doc_id, "done")
        conn.commit()
        print(f"OK {file_path} -> {doc_id}")
    except Exception as exc:  # pragma: no cover - best-effort logging
        with conn.cursor() as cur:
            mark_document(cur, doc_id, "failed", str(exc))
        conn.commit()
        print(f"FAILED {file_path}: {exc}")


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Extract DOCX core metadata into Postgres.")
    parser.add_argument("--input", required=True, help="Path to a .docx file or a folder")
    parser.add_argument("--db-url", help="Postgres URL, overrides DATABASE_URL")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    db_url = ensure_db_url(args.db_url)

    files = iter_docx_files(input_path)
    if not files:
        raise SystemExit(f"No .docx files found at {input_path}")

    with psycopg.connect(db_url) as conn:
        for file_path in files:
            process_file(conn, file_path)


if __name__ == "__main__":
    main()
