"""testing/integration/conftest.py
certPortal integration test fixtures.

Three layers:
  LAYER 1 — API     : httpx.Client (sync), psycopg2, boto3
  LAYER 2 — Browser : pytest-playwright (page, browser_context, browser — injected automatically)
  LAYER 3 — HITL    : hitl() helper — 3 modes (headed/headless/CI)

Invariants preserved:
  INV-01 / INV-07: tests never import from agents/ or call agent functions directly.
  No ORM: all DB access via psycopg2 (follows suite_f._dsn() pattern).
  S3 access via settings.ovh_s3_* — same code path as portals (MinIO ↔ OVHcloud zero-config swap).
"""
from __future__ import annotations

import os
from typing import Generator

import boto3
import httpx
import psycopg2
import pytest
from playwright.sync_api import Page

# ---------------------------------------------------------------------------
# LAYER 1 — API fixtures (httpx + psycopg2 + boto3)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def db() -> Generator[psycopg2.extensions.connection, None, None]:
    """Sync psycopg2 connection — follows suite_f._dsn() pattern.

    Requires CERTPORTAL_DB_URL in environment.
    autocommit=False so tests can roll back if needed, or commit explicitly.
    """
    conn = psycopg2.connect(os.environ["CERTPORTAL_DB_URL"])
    conn.autocommit = False
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def pam() -> Generator[httpx.Client, None, None]:
    """httpx client for Pam Admin portal (port 8000). follow_redirects=False
    so redirect assertions (status 302, Location header) work correctly."""
    with httpx.Client(base_url="http://localhost:8000", follow_redirects=False) as client:
        yield client


@pytest.fixture(scope="session")
def mer() -> Generator[httpx.Client, None, None]:
    """httpx client for Meredith Retailer portal (port 8001)."""
    with httpx.Client(base_url="http://localhost:8001", follow_redirects=False) as client:
        yield client


@pytest.fixture(scope="session")
def chrissy() -> Generator[httpx.Client, None, None]:
    """httpx client for Chrissy Supplier portal (port 8002)."""
    with httpx.Client(base_url="http://localhost:8002", follow_redirects=False) as client:
        yield client


@pytest.fixture(scope="session")
def admin_token(pam: httpx.Client) -> str:
    """JWT bearer token for pam_admin — obtained once per test session."""
    r = pam.post("/token/api", data={"username": "pam_admin", "password": "certportal_admin"})
    assert r.status_code == 200, f"admin_token fixture failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def retailer_token(mer: httpx.Client) -> str:
    """JWT bearer token for lowes_retailer — obtained once per test session."""
    r = mer.post("/token/api", data={"username": "lowes_retailer", "password": "certportal_retailer"})
    assert r.status_code == 200, f"retailer_token fixture failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def supplier_token(chrissy: httpx.Client) -> str:
    """JWT bearer token for acme_supplier — obtained once per test session."""
    r = chrissy.post("/token/api", data={"username": "acme_supplier", "password": "certportal_supplier"})
    assert r.status_code == 200, f"supplier_token fixture failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def s3_client():
    """boto3 S3 client configured from certportal settings.

    Uses settings.ovh_s3_* — works with both MinIO (local) and OVHcloud (staging/prod).
    Zero code changes to switch: just update .env.
    """
    from certportal.core.config import settings

    return boto3.client(
        "s3",
        endpoint_url=settings.ovh_s3_endpoint,
        aws_access_key_id=settings.ovh_s3_key,
        aws_secret_access_key=settings.ovh_s3_secret,
        region_name=settings.ovh_s3_region,
    )


@pytest.fixture(scope="session")
def raw_edi_bucket() -> str:
    """Name of the raw EDI S3 bucket (from settings)."""
    from certportal.core.config import settings
    return settings.ovh_s3_raw_edi_bucket


@pytest.fixture(scope="session")
def workspace_bucket() -> str:
    """Name of the agent workspace S3 bucket (from settings)."""
    from certportal.core.config import settings
    return settings.ovh_s3_workspace_bucket


# ---------------------------------------------------------------------------
# LAYER 2 — Browser helper (pytest-playwright fixtures injected automatically)
#
# pytest-playwright provides: browser, browser_context, page (function scope)
# Run with --headed to see browser; --slowmo=500 for human-paced execution.
# ---------------------------------------------------------------------------


def browser_login(page: Page, base_url: str, username: str, password: str) -> None:
    """Fill login form and submit. Waits for redirect to dashboard (/).

    Called by test files that need a pre-authenticated browser session.
    Portal login forms use input[name='username'] and input[name='password']
    with action='/token' — same HTML structure on all three portals.
    """
    page.goto(f"{base_url}/login")
    page.fill("input[name='username']", username)
    page.fill("input[name='password']", password)
    page.click("button[type='submit']")
    page.wait_for_url(f"{base_url}/")


@pytest.fixture
def pam_page(page: Page) -> Page:
    """Playwright Page pre-navigated to Pam (:8000) login page."""
    page.goto("http://localhost:8000/login")
    return page


@pytest.fixture
def mer_page(page: Page) -> Page:
    """Playwright Page pre-navigated to Meredith (:8001) login page."""
    page.goto("http://localhost:8001/login")
    return page


@pytest.fixture
def chrissy_page(page: Page) -> Page:
    """Playwright Page pre-navigated to Chrissy (:8002) login page."""
    page.goto("http://localhost:8002/login")
    return page


# ---------------------------------------------------------------------------
# LAYER 3 — HITL gate helper (3 modes)
# ---------------------------------------------------------------------------


def hitl(message: str, page: Page | None = None) -> None:
    """Human-In-The-Loop checkpoint gate.

    Mode 1 — Headed browser (--headed, CERTPORTAL_CI not set):
        If `page` is provided: calls page.pause() which opens the Playwright Inspector
        in the live browser window. Operator inspects, hovers, or clicks freely,
        then clicks ▶ Resume (or presses F8) to continue the test.

    Mode 2 — Headless / terminal (no --headed, CERTPORTAL_CI not set):
        Prints a bordered prompt to stdout and reads from stdin.
        Operator types CONTINUE to proceed, or FAIL <reason> to fail the test.

    Mode 3 — CI / unattended (CERTPORTAL_CI=true):
        pytest.skip() — HITL gate is recorded as skipped, not failed.
        P0 CI runs: pass -m "p0 and not hitl" to skip all HITL gates.

    Args:
        message: Human-readable description of what to verify.
        page:    Playwright Page object — provide for browser-visible checkpoints.
                 If None, falls back to terminal prompt.
    """
    if os.environ.get("CERTPORTAL_CI"):
        pytest.skip(f"[HITL skipped in CI] {message}")

    print(f"\n╔══ HITL CHECKPOINT ════════════════════════════════╗")
    print(f"║  {message}")
    print(f"╚════════════════════════════════════════════════════╝")

    if page is not None:
        # Headed mode: Playwright Inspector opens — operator clicks ▶ Resume to continue
        page.pause()
    else:
        # Headless mode: terminal prompt
        answer = input("  → Type CONTINUE or FAIL <reason>: ").strip().upper()
        if not answer.startswith("CONTINUE"):
            pytest.fail(f"Operator rejected HITL gate: {answer}")
