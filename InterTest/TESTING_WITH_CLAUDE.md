# Running certPortal Integration Tests with Claude Code CLI

This guide walks through every step required to run the 16 real-life test
scenarios in `real-life-test-scenarios.md` using the **Claude Code CLI**
(`claude`) as your testing agent.

---

## How it works

The `test-runner` skill is installed in `.claude/skills/test-runner/SKILL.md`.
When you open Claude Code in this project and ask it to run a scenario, Claude:

1. Looks up the scenario ID in the skill's file map
2. Runs the appropriate `pytest` command in your terminal
3. Streams live output so you can watch tests pass/fail in real time
4. Pauses at every **`[HITL]`** checkpoint and asks you to verify before continuing

You do not write or run any pytest commands yourself — you just talk to Claude.

---

## Part 1 — One-Time Setup

These steps are done **once per machine**. Skip any you have already completed.

### 1.1 Install pytest-playwright's browser binary

```bash
playwright install chromium
```

This downloads the Chromium binary that Playwright uses for browser tests.
It is separate from installing the Python package (which is already in
`requirements.txt`).

### 1.2 Start MinIO (local S3)

The test suite uses MinIO as a local replacement for OVHcloud S3.

```bash
docker compose -f docker-compose.minio.yml up -d
```

Verify it is healthy:

```bash
curl -s http://localhost:9000/minio/health/live && echo " MinIO OK"
```

### 1.3 Switch `.env` to MinIO

```bash
cp .env.minio.example .env
```

This sets `OVH_S3_ENDPOINT=http://localhost:9000` so all portals and tests
hit your local MinIO instead of OVHcloud. No code changes needed — the portals
read `settings.ovh_s3_*` from `.env` at startup.

> **Switching back to OVHcloud:** restore your original `.env` with the real
> `OVH_S3_KEY` / `OVH_S3_SECRET` values. Zero code changes required.

### 1.4 Apply all database migrations

```bash
export CERTPORTAL_DB_URL=postgresql://certportal:certportal@localhost:5432/certportal

psql $CERTPORTAL_DB_URL -f lifecycle_engine/migrations/001_lifecycle_tables.sql
psql $CERTPORTAL_DB_URL -f migrations/001_app_tables.sql
psql $CERTPORTAL_DB_URL -f migrations/002_users_table.sql
psql $CERTPORTAL_DB_URL -f migrations/003_patch_reject.sql
psql $CERTPORTAL_DB_URL -f migrations/004_revoked_tokens.sql
psql $CERTPORTAL_DB_URL -f migrations/005_password_reset.sql
```

All migrations are idempotent — safe to re-run if you are unsure.

### 1.5 Create S3 buckets and upload EDI fixtures

```bash
python testing/integration/setup_minio.py
```

This script (run once per environment) creates the two required buckets and
uploads `THESIS.md` plus all 5 EDI fixture files to MinIO. Output:

```
Created bucket: certportal-workspaces
Created bucket: certportal-raw-edi
Uploaded: lowes/acme/850/test_850_pass.edi
Uploaded: lowes/acme/850/test_850_fail.edi
...
Setup complete.
```

---

## Part 2 — Before Every Test Session

These checks take under a minute and prevent confusing failures mid-run.

### 2.1 Verify PostgreSQL is running

```bash
psql $CERTPORTAL_DB_URL -c "SELECT 1" -q
```

Expected: `1` (one row). If it errors, start your Docker Postgres container.

### 2.2 Start the three portals

Open **three separate terminals** (or use a process manager):

```bash
# Terminal 1
uvicorn portals.pam:app --port 8000

# Terminal 2
uvicorn portals.meredith:app --port 8001

# Terminal 3
uvicorn portals.chrissy:app --port 8002
```

Or if you have `honcho` installed:

```bash
# Starts all three via Procfile (uses $PORT — set manually for local dev)
PAM_PORT=8000 MEREDITH_PORT=8001 CHRISSY_PORT=8002 honcho start
```

Spot-check that all three are alive:

```bash
curl -s http://localhost:8000/health && \
curl -s http://localhost:8001/health && \
curl -s http://localhost:8002/health
```

Expected output (one line per portal):
```
{"status":"ok","portal":"pam","version":"1.0.0"}
{"status":"ok","portal":"meredith","version":"1.0.0"}
{"status":"ok","portal":"chrissy","version":"1.0.0"}
```

### 2.3 Preflight collection check

```bash
pytest testing/integration/ --collect-only -q
```

Expected: `138 tests collected, 0 errors`. If this fails, there is an import
error in a test file — fix it before proceeding.

---

## Part 3 — Opening Claude Code

```bash
cd /path/to/certPortalCombo
claude
```

Claude Code opens in your terminal. The `test-runner` skill is automatically
available because it lives in `.claude/skills/test-runner/SKILL.md`.

You are now talking to your testing agent. Everything from here is a
conversation.

---

## Part 4 — Running Scenarios

### Trigger phrases

Say any of these to start a test run:

| What you say | What Claude runs |
|---|---|
| `run PAM-01` | `pytest testing/integration/test_pam_01.py -v` |
| `run scenario CHR-03` | `pytest testing/integration/test_chr_03.py -v` |
| `run E2E-01 headed` | `pytest testing/integration/test_e2e_01.py -v --headed --slowmo=500` |
| `test all P0 scenarios` | `pytest testing/integration/ -v -m "p0"` |
| `run all integration tests` | `pytest testing/integration/ -v --headed --slowmo=300` |
| `run the supplier tests` | PAM + CHR group |
| `run P0 in CI mode` | `CERTPORTAL_CI=true pytest ... -m "p0 and not hitl"` |
| `what failed in MER-02?` | Runs MER-02 and explains failures |
| `run interactive tests` | Full suite with `--headed --slowmo=500` |

### Choose your HITL mode

Before running any scenario that has `[HITL]` checkpoints, tell Claude which
mode you want:

| Mode | What to say | What happens at HITL gates |
|------|-------------|---------------------------|
| **Headed** | `run PAM-02 headed` | Playwright Inspector opens in a visible Chrome window — you click ▶ Resume |
| **Headless** | `run PAM-02` | Claude prints a checkpoint prompt in the terminal — you type `CONTINUE` or `FAIL` |
| **CI / unattended** | `run PAM-02 CI mode` | All `[HITL]` checkpoints are skipped automatically |

---

## Part 5 — Seed SQL (run before the first time each scenario group is tested)

Some scenarios need specific database state. Run the seed files once before
the corresponding scenario if the state is stale or missing:

```bash
# Before PAM-02 — seeds two HITL queue items
psql $CERTPORTAL_DB_URL -f testing/fixtures/sql/seed_hitl_queue.sql

# Before PAM-03, E2E-01, E2E-02, E2E-03 — resets acme gates to PENDING
psql $CERTPORTAL_DB_URL -f testing/fixtures/sql/reset_gates.sql

# Before CHR-01, CHR-03 — seeds one PASS + one FAIL test_occurrence
psql $CERTPORTAL_DB_URL -f testing/fixtures/sql/seed_test_occurrences.sql

# Before CHR-04 — seeds two patch_suggestions rows
psql $CERTPORTAL_DB_URL -f testing/fixtures/sql/seed_patch_suggestions.sql

# Before E2E-01, E2E-02, E2E-03 — removes all PO-E2E-* and bolt supplier data
psql $CERTPORTAL_DB_URL -f testing/fixtures/sql/clean_e2e.sql
```

> **Tip:** Ask Claude — it knows which seeds each scenario needs:
> `"What do I need to seed before running CHR-04?"`

---

## Part 6 — HITL Checkpoint Interaction

### Headed mode (recommended for first runs)

When Claude reaches a `[HITL]` checkpoint:

1. A Chromium window opens (or is already open from the test run)
2. The **Playwright Inspector** panel appears in the browser window
3. The terminal shows the checkpoint description — read it carefully
4. Inspect the live page — hover, scroll, read the content
5. When satisfied, click **▶ Resume** in the Inspector panel (or press **F8**)
6. The test continues

If something is wrong, click **✕ Stop** in the Inspector to abort the test,
then tell Claude what you observed.

### Headless mode

When Claude reaches a `[HITL]` checkpoint, the terminal pauses and prints:

```
╔══ HITL CHECKPOINT ════════════════════════════════╗
║  <description of what to check>
╚════════════════════════════════════════════════════╝
  → Type CONTINUE or FAIL <reason>:
```

- Open a browser at the URL shown and inspect the page yourself
- Type `CONTINUE` and press Enter if everything looks correct
- Type `FAIL the error message text was cut off` (or any reason) to fail the test

### The 6 true HITL checkpoints

These are the moments that genuinely require your eyes and judgment:

| Scenario | What to look for |
|----------|-----------------|
| **PAM-02** | Read the two Kelly draft emails in the HITL queue. The first should be a professional validation failure notice. The second should be aggressive and inappropriate. Confirm your read before approving/rejecting. |
| **PAM-04** | Check your actual email inbox for `pam_admin`'s account. Confirm the password reset link email arrived and contains a valid reset URL. |
| **CHR-03** | Open `http://localhost:8002/errors` as `acme_supplier`. Confirm the two error messages (BEG03 and ISA13) are human-readable and actionable — not raw codes or stack traces. |
| **CHR-04** | Open the patch content viewer. Read the proposed YAML fix for each error. Decide which patch makes logical sense to apply and which to reject. |
| **E2E-01** (start) | Open `http://localhost:8001/spec-setup` as `lowes_retailer`. Confirm the Lowe's EDI spec shown is the current version — not a stale draft. |
| **E2E-01** (end) | Open all three portals. Confirm: Chrissy dashboard shows CERTIFIED badge, Pam suppliers list shows CERTIFIED for acme, Meredith `certified_count` increased by 1. |

All other checkpoint bullets tagged `[AUTO]` in `real-life-test-scenarios.md`
are verified by code assertions inside the test files — you do not need to
check them manually.

---

## Part 7 — Example Sessions

### Quick P0 smoke run (CI mode, no browser, no HITL)

```
You:   run all P0 scenarios in CI mode

Claude: Running: CERTPORTAL_CI=true pytest testing/integration/ -v -m "p0 and not hitl"
        [streams pytest output]
        ✓ 89 passed, 12 skipped (HITL gates), 0 failed
```

### Single scenario with browser (interactive)

```
You:   run PAM-03 headed

Claude: Seeding acme gates to PENDING...
        Running: pytest testing/integration/test_pam_03.py -v --headed --slowmo=500
        [Chromium window opens]
        [tests run with 500ms delay so you can follow along]
        [all assertions pass — no HITL gates in PAM-03]
        ✓ 6 passed
```

### Scenario with a HITL checkpoint (headless)

```
You:   run PAM-02

Claude: Seeding hitl_queue...
        Running: pytest testing/integration/test_pam_02.py -v

        ╔══ HITL CHECKPOINT ════════════════════════════════╗
        ║  Read both queued items. Confirm 'test-hitl-approve-001'
        ║  contains a professional draft and 'test-hitl-reject-001'
        ║  contains an inappropriate one. Decide: approve 001, reject 002.
        ╚════════════════════════════════════════════════════╝
          → Type CONTINUE or FAIL <reason>:

You:   CONTINUE

Claude: [test resumes — approve/reject steps execute]
        ✓ 7 passed
```

### Diagnosing a failure

```
You:   what failed in MER-02?

Claude: Running: pytest testing/integration/test_mer_02.py -v
        FAILED test_mer_02.py::TestMER02::test_valid_upload_writes_s3_signal
          AssertionError: No S3 signal found at prefix lowes/system/signals/
          Bucket certportal-workspaces is empty.

        The MinIO bucket exists but setup_minio.py hasn't been run, or
        the .env still points at OVHcloud (OVH_S3_KEY is blank).
        Run: python testing/integration/setup_minio.py
        Then check .env has OVH_S3_ENDPOINT=http://localhost:9000
```

### Full E2E with HITL (headed, one scenario at a time)

```
You:   run E2E-01 headed

Claude: Resetting acme gates + cleaning E2E state...
        Running: pytest testing/integration/test_e2e_01.py -v --headed --slowmo=500

        [HITL-1 — Playwright Inspector opens on Meredith spec-setup page]
        [You review the spec, press ▶ Resume]

        [automated: 4× Moses runs, 3× gate completions, certify]

        [HITL-2 — Playwright Inspector opens on Chrissy dashboard]
        [You confirm CERTIFIED badge, press ▶ Resume]

        ✓ 14 passed, 2 skipped (CI-only gates)
```

---

## Part 8 — Scenario Groups Quick Reference

| Group | Command to Claude | Scenarios | Tests |
|-------|-------------------|-----------|-------|
| Platform (all) | `run all platform tests` | PAM-01–04 | ~38 |
| Platform P0 | `run platform P0 tests` | PAM-01–03 | ~29 |
| Retailer (all) | `run all retailer tests` | MER-01–04 | ~32 |
| Supplier (all) | `run the supplier tests` | CHR-01–05 | ~42 |
| Supplier P0 | `run supplier P0 tests` | CHR-01–03, CHR-05 | ~34 |
| E2E (all) | `run all E2E tests` | E2E-01–03 | ~26 |
| E2E P0 | `run E2E P0 tests` | E2E-01, E2E-02 | ~20 |
| Full P0 | `test all P0 scenarios` | All P0 | ~89 |
| Full suite | `run all integration tests` | All 16 | 138 |

---

## Part 9 — Troubleshooting

### "138 tests" becomes fewer in `--collect-only`

A test file has an import error. Run:
```bash
pytest testing/integration/ --collect-only -q 2>&1 | grep "ERROR"
```
Fix the import, then re-run the collection check.

### Portal returns `Connection refused`

One of the three portals is not running. Start it:
```bash
uvicorn portals.pam:app --port 8000      # or 8001 / 8002
```

### `ThesisMissing` error in CHR-02/CHR-05/E2E tests

The `THESIS.md` file is not in MinIO. Re-run setup:
```bash
python testing/integration/setup_minio.py
```

### `S3 signal not found` in MER-02/MER-03

The `.env` still points at OVHcloud with blank credentials. Check:
```bash
grep OVH_S3_ENDPOINT .env
```
Should be `http://localhost:9000`. If not, run `cp .env.minio.example .env`
and restart the portals.

### HITL gate fires in CI mode unexpectedly

You have `CERTPORTAL_CI=true` set but also `--headed`. The `CERTPORTAL_CI` env
var takes precedence — HITL tests will be skipped regardless of `--headed`.
Remove the env var for interactive runs.

### Playwright Inspector does not open

You are running headless (no `--headed` flag). Either add `--headed` to the
command, or use headless terminal-prompt mode (just type `CONTINUE` in the
terminal).

### Gate tests fail with 409 when they should pass

The `acme` gates are not in PENDING state from a previous run. Reset them:
```bash
psql $CERTPORTAL_DB_URL -f testing/fixtures/sql/reset_gates.sql
```
Or ask Claude: `"Reset the acme gates before running PAM-03"`.

### E2E tests fail with duplicate PO number errors

Leftover state from a previous E2E run. Clean it:
```bash
psql $CERTPORTAL_DB_URL -f testing/fixtures/sql/clean_e2e.sql
```

---

## Dev Seed Credentials (local only)

| User | Password | Role | Portal |
|------|----------|------|--------|
| `pam_admin` | `certportal_admin` | admin | Pam — http://localhost:8000 |
| `lowes_retailer` | `certportal_retailer` | retailer | Meredith — http://localhost:8001 |
| `acme_supplier` | `certportal_supplier` | supplier | Chrissy — http://localhost:8002 |

---

---

## Part 10 — Anti-Hallucination Safeguards

Every scenario in `real-life-test-scenarios.md` (v1.2) embeds these protections:

1. **SELF-CHECK block** — each prompt starts with prerequisite health/SQL checks. If any fail, the agent stops immediately rather than proceeding with guessed state.
2. **ANTI-HALLUCINATION RULES** — scenario-specific reminders embedded in every prompt (e.g., "verify via SQL after every POST", "do not trust HTTP 200 alone").
3. **DB-is-truth principle** — every write operation is followed by a verification read. The agent must not report PASS based on HTTP response alone.
4. **`[AUTO]` vs `[HITL]` tagging** — code-assertable checks are run by pytest; human-judgment checks require operator eyes. Neither can substitute for the other.
5. **Operator override** — at every HITL checkpoint, the operator can independently run the listed SQL queries. If the operator's check disagrees with the agent's report, the test fails.

---

*For the full scenario descriptions and checkpoint details, see
`real-life-test-scenarios.md` (v1.2). For the raw pytest commands, see
`.claude/skills/test-runner/SKILL.md`.*
