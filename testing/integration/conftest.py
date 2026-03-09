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
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

import boto3
import httpx
import psycopg2
import pytest
from playwright.sync_api import Page


# ---------------------------------------------------------------------------
# HITL session notes — collected across all HITL gates, persisted at session end
# ---------------------------------------------------------------------------

_hitl_notes: list[dict] = []


# ---------------------------------------------------------------------------
# Shared assertion helper (used by all 16 test files)
# ---------------------------------------------------------------------------


def assert_status(response: httpx.Response, expected: int, *, msg: str = "") -> None:
    """Assert HTTP response status with rich context on failure.

    Usage:
        assert_status(r, 200, msg="POST /token/api login")
    """
    assert response.status_code == expected, (
        f"{msg + ' — ' if msg else ''}"
        f"Expected {expected}, got {response.status_code}\n"
        f"URL: {response.url}\n"
        f"Body: {response.text[:500]}"
    )

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


@pytest.fixture(autouse=True)
def _db_savepoint(db: psycopg2.extensions.connection):
    """Wrap each test in a SAVEPOINT for automatic rollback of direct DB writes.

    This protects against cross-test contamination from seed data and cleanup
    queries written via db.cursor().execute().

    **Known limitation:** Portal HTTP writes use their own DB connections (asyncpg),
    so writes made *through the portal API* during a test are NOT rolled back by
    this fixture. The SAVEPOINT only protects direct psycopg2 writes in tests
    (seed data, cleanup queries). This is expected — portal writes represent
    real application state changes being tested.
    """
    cur = db.cursor()
    cur.execute("SAVEPOINT test_sp")
    yield
    try:
        cur.execute("ROLLBACK TO SAVEPOINT test_sp")
    except Exception:
        db.rollback()


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
def _portals_healthy(pam: httpx.Client, mer: httpx.Client, chrissy: httpx.Client) -> None:
    """Check /health on all 3 portals — SKIP (not ERROR) if any portal is unreachable.

    Without this guard, a down portal causes the token fixtures to raise,
    which cascade-fails ~95/138 tests with ERROR rather than SKIP.
    """
    for name, client in [("pam", pam), ("meredith", mer), ("chrissy", chrissy)]:
        try:
            r = client.get("/health", timeout=5)
            assert r.status_code == 200, f"{name} /health returned {r.status_code}"
        except Exception as exc:
            pytest.skip(f"{name} portal unreachable: {exc}")


@pytest.fixture(scope="session")
def admin_token(_portals_healthy: None, pam: httpx.Client) -> str:
    """JWT bearer token for pam_admin — obtained once per test session.

    Depends on _portals_healthy: if Pam is down, tests SKIP instead of ERROR.
    """
    r = pam.post("/token/api", data={"username": "pam_admin", "password": "certportal_admin"})
    assert_status(r, 200, msg="admin_token fixture — POST /token/api")
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def retailer_token(_portals_healthy: None, mer: httpx.Client) -> str:
    """JWT bearer token for lowes_retailer — obtained once per test session.

    Depends on _portals_healthy: if Meredith is down, tests SKIP instead of ERROR.
    """
    r = mer.post("/token/api", data={"username": "lowes_retailer", "password": "certportal_retailer"})
    assert_status(r, 200, msg="retailer_token fixture — POST /token/api")
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def supplier_token(_portals_healthy: None, chrissy: httpx.Client) -> str:
    """JWT bearer token for acme_supplier — obtained once per test session.

    Depends on _portals_healthy: if Chrissy is down, tests SKIP instead of ERROR.
    """
    r = chrissy.post("/token/api", data={"username": "acme_supplier", "password": "certportal_supplier"})
    assert_status(r, 200, msg="supplier_token fixture — POST /token/api")
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


def hitl(message: str, page: Page | None = None, *, scenario: str = "") -> None:
    """Human-In-The-Loop checkpoint gate.

    Mode 1 — Headed browser (--headed, CERTPORTAL_CI not set):
        If `page` is provided: calls page.pause() which opens the Playwright Inspector
        in the live browser window. Operator inspects, hovers, or clicks freely,
        then clicks ▶ Resume (or presses F8) to continue the test.

    Mode 2 — Headless / terminal (no --headed, CERTPORTAL_CI not set):
        Prints a bordered prompt to stdout and reads from stdin.
        Operator types CONTINUE to proceed, or FAIL <reason> to fail the test.
        Additional commands accepted:
          BUG <text>  — log a bug observation (test continues)
          NOTE <text> — log a note/observation (test continues)

    Mode 3 — CI / unattended (CERTPORTAL_CI=true):
        pytest.skip() — HITL gate is recorded as skipped, not failed.
        P0 CI runs: pass -m "p0 and not hitl" to skip all HITL gates.

    Args:
        message:  Human-readable description of what to verify.
        page:     Playwright Page object — provide for browser-visible checkpoints.
                  If None, falls back to terminal prompt.
        scenario: Scenario ID (e.g. "PAM-02") for note attribution.
    """
    if os.environ.get("CERTPORTAL_CI"):
        pytest.skip(f"[HITL skipped in CI] {message}")

    print(f"\n╔══ HITL CHECKPOINT ════════════════════════════════╗")
    print(f"║  {message}")
    print(f"╚════════════════════════════════════════════════════╝")
    print(f"  Commands: CONTINUE | FAIL <reason> | BUG <text> | NOTE <text>")

    if page is not None:
        # Headed mode: Playwright Inspector opens — operator clicks ▶ Resume to continue
        page.pause()
    else:
        # Headless mode: terminal prompt with note capture loop
        while True:
            answer = input("  → ").strip()
            upper = answer.upper()

            if upper.startswith("CONTINUE"):
                break
            elif upper.startswith("FAIL"):
                reason = answer[4:].strip() or "Operator rejected"
                pytest.fail(f"Operator rejected HITL gate: {reason}")
            elif upper.startswith("BUG ") or upper.startswith("NOTE "):
                kind = "bug" if upper.startswith("BUG") else "note"
                text = answer[4:].strip()
                _hitl_notes.append({
                    "kind": kind,
                    "scenario": scenario,
                    "checkpoint": message[:80],
                    "text": text,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                print(f"  ✓ {kind.upper()} captured. Type CONTINUE to proceed or add more.")
            else:
                print("  ⚠ Unknown command. Use CONTINUE, FAIL, BUG, or NOTE.")


# ---------------------------------------------------------------------------
# LAYER 4 — pytest-html screenshot-on-failure hook
# ---------------------------------------------------------------------------


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture a Playwright screenshot when a browser-based test fails.

    Screenshots are saved to test-results/screenshots/ and attached to the
    pytest-html report as inline images (if pytest-html is installed).
    """
    from pathlib import Path

    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:
        page = item.funcargs.get("page")
        if page:
            screenshot_dir = Path("test-results/screenshots")
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            safe_name = item.nodeid.replace("/", "_").replace("::", "_").replace("\\", "_")
            path = screenshot_dir / f"{safe_name}.png"
            try:
                page.screenshot(path=str(path))
            except Exception:
                pass  # page may have closed already
            else:
                # Attach to pytest-html report if available
                try:
                    import pytest_html  # type: ignore[import]
                    extras = getattr(report, "extras", [])
                    extras.append(pytest_html.extras.image(str(path)))
                    report.extras = extras
                except ImportError:
                    pass


# ---------------------------------------------------------------------------
# LAYER 5 — HITL session notes persistence + GitHub Issues auto-filing
# ---------------------------------------------------------------------------


def pytest_sessionfinish(session, exitstatus):
    """Persist HITL notes to markdown and optionally file GitHub Issues.

    Notes are always written to test-results/hitl-session-summary.md.
    If GITHUB_TOKEN and GITHUB_REPO env vars are set, bugs are also filed
    as GitHub Issues via the REST API.
    """
    if not _hitl_notes:
        return

    results_dir = Path("test-results")
    results_dir.mkdir(parents=True, exist_ok=True)
    summary_path = results_dir / "hitl-session-summary.md"

    # Write markdown summary
    lines = ["# HITL Session Notes\n\n"]
    lines.append(f"**Session:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n")
    lines.append(f"**Notes collected:** {len(_hitl_notes)}\n\n")

    for note in _hitl_notes:
        kind_label = "🐛 BUG" if note["kind"] == "bug" else "📝 NOTE"
        lines.append(f"### {kind_label} — {note.get('scenario', 'unknown')}\n\n")
        lines.append(f"**Checkpoint:** {note['checkpoint']}\n\n")
        lines.append(f"{note['text']}\n\n")
        lines.append(f"*{note['timestamp']}*\n\n---\n\n")

    summary_path.write_text("".join(lines), encoding="utf-8")

    # Optionally file GitHub Issues for bugs
    gh_token = os.environ.get("GITHUB_TOKEN")
    gh_repo = os.environ.get("GITHUB_REPO")  # e.g. "owner/repo"

    if gh_token and gh_repo:
        bugs = [n for n in _hitl_notes if n["kind"] == "bug"]
        if bugs:
            try:
                _file_github_issues(bugs, gh_token, gh_repo)
            except Exception as exc:
                print(f"\n⚠ Failed to file GitHub Issues: {exc}")
                print(f"  Notes are still saved at: {summary_path}")


def _file_github_issues(bugs: list[dict], token: str, repo: str) -> None:
    """File GitHub Issues for each HITL bug note via REST API."""
    api_url = f"https://api.github.com/repos/{repo}/issues"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    for bug in bugs:
        scenario = bug.get("scenario", "unknown")
        first_line = bug["text"].split("\n")[0][:80]
        title = f"[HITL] {scenario}: {first_line}"

        body = (
            f"## HITL Bug Report\n\n"
            f"**Scenario:** {scenario}\n"
            f"**Checkpoint:** {bug['checkpoint']}\n"
            f"**Timestamp:** {bug['timestamp']}\n\n"
            f"### Description\n\n{bug['text']}\n\n"
            f"---\n"
            f"*Auto-filed by certPortal HITL test session.*"
        )

        resp = httpx.post(
            api_url,
            headers=headers,
            json={
                "title": title,
                "body": body,
                "labels": ["hitl", "bug"],
            },
            timeout=15,
        )
        if resp.status_code == 201:
            issue_url = resp.json().get("html_url", "")
            print(f"  ✓ Filed: {title} → {issue_url}")
        else:
            print(f"  ⚠ Failed to file issue: {resp.status_code} {resp.text[:200]}")
