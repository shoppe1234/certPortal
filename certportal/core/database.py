"""certportal/core/database.py — Async PostgreSQL connection pool via asyncpg.

PostgreSQL Schema Reference (do not run automatically — apply via migration tool):

    CREATE TABLE retailer_specs (
        id            SERIAL PRIMARY KEY,
        retailer_slug TEXT NOT NULL,
        spec_version  TEXT NOT NULL,
        thesis_s3_key TEXT NOT NULL,
        source_pdf_key TEXT,
        created_at    TIMESTAMPTZ DEFAULT now()
    );

    CREATE TABLE test_occurrences (
        id               SERIAL PRIMARY KEY,
        supplier_slug    TEXT NOT NULL,
        retailer_slug    TEXT NOT NULL,
        transaction_type TEXT NOT NULL,
        channel          TEXT NOT NULL,
        status           TEXT NOT NULL CHECK (status IN ('PASS', 'FAIL', 'PARTIAL')),
        validated_at     TIMESTAMPTZ DEFAULT now(),
        result_json      JSONB NOT NULL
    );

    CREATE TABLE patch_suggestions (
        id            SERIAL PRIMARY KEY,
        supplier_slug TEXT NOT NULL,
        retailer_slug TEXT NOT NULL,
        error_code    TEXT NOT NULL,
        segment       TEXT NOT NULL,
        element       TEXT,
        summary       TEXT NOT NULL,
        patch_s3_key  TEXT NOT NULL,
        applied       BOOLEAN DEFAULT FALSE,
        created_at    TIMESTAMPTZ DEFAULT now()
    );

    CREATE TABLE monica_memory (
        id            SERIAL PRIMARY KEY,
        timestamp     TIMESTAMPTZ NOT NULL,
        agent         TEXT NOT NULL,
        direction     TEXT NOT NULL CHECK (direction IN ('Q', 'A')),
        message       TEXT NOT NULL,
        retailer_slug TEXT,
        supplier_slug TEXT
    );

    CREATE TABLE hitl_gate_status (
        supplier_id    TEXT PRIMARY KEY,
        gate_1         TEXT NOT NULL DEFAULT 'PENDING',
        gate_2         TEXT NOT NULL DEFAULT 'PENDING',
        gate_3         TEXT NOT NULL DEFAULT 'PENDING',
        last_updated   TIMESTAMPTZ DEFAULT now(),
        last_updated_by TEXT NOT NULL
    );

    CREATE TABLE seen_scenarios (
        id            SERIAL PRIMARY KEY,
        supplier_slug TEXT NOT NULL,
        retailer_slug TEXT NOT NULL,
        scenario_id   TEXT NOT NULL,
        UNIQUE (supplier_slug, retailer_slug, scenario_id)
    );

    CREATE TABLE hitl_queue (
        id            SERIAL PRIMARY KEY,
        queue_id      TEXT UNIQUE NOT NULL,
        retailer_slug TEXT NOT NULL,
        supplier_slug TEXT NOT NULL,
        agent         TEXT NOT NULL,
        draft         TEXT NOT NULL,
        summary       TEXT,
        thread_id     TEXT,
        channel       TEXT,
        status        TEXT NOT NULL DEFAULT 'PENDING_APPROVAL',
        queued_at     TIMESTAMPTZ DEFAULT now(),
        resolved_at   TIMESTAMPTZ,
        resolved_by   TEXT
    );
"""
import asyncpg

from certportal.core.config import settings

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Return (or create) the shared async connection pool."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            settings.certportal_db_url,
            min_size=2,
            max_size=10,
        )
    return _pool


async def get_connection():
    """Async generator yielding a DB connection from the pool.

    Usage (in FastAPI route via Depends):
        async def route(conn=Depends(get_connection)):
            ...
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn
