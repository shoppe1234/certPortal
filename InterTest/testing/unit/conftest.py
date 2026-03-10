"""
testing/unit/conftest.py — Shared fixtures for migrated unit test suites (A-I).

Most unit tests are fully mocked and need no fixtures. Suite F needs live Postgres.
"""
import os
import pytest


@pytest.fixture(scope="session")
def db_dsn():
    """Return CERTPORTAL_DB_URL or skip if not set (Suite F only)."""
    dsn = os.environ.get("CERTPORTAL_DB_URL", "")
    if not dsn:
        pytest.skip("CERTPORTAL_DB_URL not set — cannot run lifecycle engine tests")
    return dsn
