# Parallel Test Safety Guide

## Current State

Tests run **sequentially** by default. This document prepares for future
`pytest-xdist` adoption by documenting which tests are parallel-safe and
which require serial execution.

## Marker: `@pytest.mark.serial`

Tests marked `@pytest.mark.serial` mutate shared database state and **must
not** run in parallel with other tests. When `pytest-xdist` is adopted,
these tests should run in a dedicated worker or via `--dist=loadscope`.

## Unit Tests (`testing/unit/`)

**All 103 unit tests are parallel-safe.** They use mocked DB/S3/OpenAI and
have no shared state. The only exception is Suite F (`test_lifecycle_engine.py`),
which requires a live Postgres connection but uses isolated PO numbers
prefixed with `IT-*` and cleans up in `setup_class`.

## Integration Tests (`testing/integration/`)

### Parallel-Safe (read-only or idempotent)

| File | Tests | Why Safe |
|------|-------|----------|
| `test_pam_01.py` | 7 | Read-only: health, login, token decode, permissions |
| `test_mer_01.py` | 8 | Read-only: health, login, dashboard, navigation |
| `test_chr_01.py` | 11 | Read-only: health, login, dashboard, gate status |
| `test_chr_02.py` | 8 | Read-only: scenarios page, 850 pass data display |
| `test_chr_05.py` | 8 | Read-only: 855/856/810 submission page views |

### Serial (shared state mutation)

| File | Tests | Why Serial | State Mutated |
|------|-------|-----------|---------------|
| `test_pam_02.py` | 7 | HITL queue approve/reject changes queue state | `hitl_queue` rows |
| `test_pam_03.py` | 6 | Gate progression changes gate state | `hitl_gate_status` |
| `test_pam_04.py` | 5 | Password reset changes user password | `portal_users` |
| `test_mer_02.py` | 4 | Spec upload writes S3 signals | S3 workspace bucket |
| `test_mer_03.py` | 6 | YAML wizard creates workspace files | S3 workspace bucket |
| `test_mer_04.py` | 4 | Change password modifies user hash | `portal_users` |
| `test_chr_03.py` | 6 | Error page relies on injected test data | `test_occurrences` |
| `test_chr_04.py` | 7 | Patch apply/reject changes patch state | `patch_suggestions` |
| `test_e2e_01.py` | 14 | Full E2E: gates + all tx types | All tables |
| `test_e2e_02.py` | 6 | Failure recovery: gates + error data | `hitl_gate_status` |
| `test_e2e_03.py` | 8 | New supplier: creates user + gates | `portal_users`, `hitl_gate_status` |

### DB Isolation Strategy

The `_db_savepoint` autouse fixture (conftest.py) wraps each test in a
PostgreSQL SAVEPOINT for automatic rollback of direct `db.cursor()` writes.

**Known limitation:** Portal API writes use their own asyncpg connections,
so writes made through the HTTP API are NOT rolled back. The SAVEPOINT
only protects direct psycopg2 writes in test setup/cleanup code.

## Future: Adopting pytest-xdist

When ready to parallelize:

1. Install: `pip install pytest-xdist`
2. Run parallel-safe tests: `pytest testing/ -n auto -m "not serial"`
3. Run serial tests after: `pytest testing/ -m "serial"`
4. Or use loadscope: `pytest testing/ -n auto --dist=loadscope`
   (all tests in a class run on the same worker)

**Do NOT enable xdist until PR 4 (DB Transaction Isolation) is proven stable.**
