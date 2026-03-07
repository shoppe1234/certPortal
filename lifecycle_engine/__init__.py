"""
lifecycle_engine — Order-to-Cash state machine runtime for certPortal.

Public API (imported by pipeline.py hook via ImportError guard):
    from lifecycle_engine.interface import on_document_processed

Internal modules:
    exceptions  — All exception classes
    loader      — YAML framework loader (order_to_cash.yaml)
    state_store — Postgres persistence (psycopg2, no ORM)
    validators  — Business rule validators
    s3_writer   — S3 violation writer (uses S3AgentWorkspace)
    engine      — LifecycleEngine orchestrator
    interface   — Public callable on_document_processed()
"""
