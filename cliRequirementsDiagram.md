# certPortal Requirements Verification — Complete System Diagram

## Execution Flow

```
  python -m playwrightcli --portal all --verify
         |
         v
  +----------------+     +----------------------------------------------+
  |  cli.py        |---->|  Pre-flight: GET /health on each portal      |
  |  --verify      |     +----------------------------------------------+
  |  --observe     |                        |
  |  --dry-run     |                        v
  +-------+--------+     +----------------------------------------------+
         |               |  Create per-portal RequirementsVerifier       |
         |               |  Create StepRunner + MemoryManager            |
         |               +----------------------------------------------+
         |                                |
         v                                v
  +-----------------------------------------------------------------+
  |                    FOR EACH PORTAL                               |
  |  +-----------+  +-------------+  +--------------+               |
  |  |  PAM      |  |  MEREDITH   |  |  CHRISSY     |               |
  |  |  :8000    |  |  :8001      |  |  :8002       |               |
  |  |  admin    |  |  retailer   |  |  supplier    |               |
  |  +-----+-----+  +------+------+  +------+-------+               |
  |        +---------------+------------------+                      |
  |                        v                                         |
  |  +---------------------------------------------------------+    |
  |  |              FLOW EXECUTION (per step)                   |    |
  |  |                                                          |    |
  |  |   +----------+    +----------+    +------------------+   |    |
  |  |   | run_step |--->| capture  |--->|     verify       |   |    |
  |  |   | (runner) |    |(observer)|    |  (requirements)  |   |    |
  |  |   +----------+    +----------+    +--------+---------+   |    |
  |  |        |               |                   |              |    |
  |  |        |               |                   v              |    |
  |  |        |               |          +-----------------+     |    |
  |  |        |               |          |  DOM Assertions  |    |    |
  |  |        |               |          |  on live page:   |    |    |
  |  |        |               |          |  - selectors     |    |    |
  |  |        |               |          |  - text content  |    |    |
  |  |        |               |          |  - element count |    |    |
  |  |        |               |          |  PASS / FAIL /   |    |    |
  |  |        |               |          |  SKIP per req ID |    |    |
  |  |        |               |          +-----------------+     |    |
  |  |        |               |                                  |    |
  |  +--------+---------------+----------------------------------+    |
  +------------+---------------+--------------------------------------+
               |               |
               v               v
  +------------------------------------------------------------------+
  |                     OUTPUT LAYER                                   |
  |                                                                    |
  |  STEP CORRECTIONS              DESIGN OBSERVER                    |
  |  (existing system)             (--observe)                        |
  |  +--------------+              +------------------+               |
  |  | feedback.md  |              | screenshots/     |               |
  |  | memory.md    |              | design_reviews/  |               |
  |  +--------------+              +------------------+               |
  |                                                                    |
  |  REQUIREMENTS VERIFICATION (--verify)                             |
  |  +------------------------------------------------------------+   |
  |  |                                                             |   |
  |  |  IMMEDIATE (per run)          PERSISTENT (across N runs)    |   |
  |  |  +--------------------+       +----------------------+      |   |
  |  |  | requirements_      |       | requirements_        |      |   |
  |  |  | reports/           |       | feedback.md          |      |   |
  |  |  |  summary_{ts}.md   |       | (append-only log)    |      |   |
  |  |  |  requirements_     |       +----------+-----------+      |   |
  |  |  |   pam_{ts}.md      |                  |                  |   |
  |  |  |   meredith_{ts}.md |                  v                  |   |
  |  |  |   chrissy_{ts}.md  |       +----------------------+      |   |
  |  |  +--------------------+       | requirements_        |      |   |
  |  |                               | history.jsonl        |      |   |
  |  |                               | (1 JSON per run)     |      |   |
  |  |                               +----------+-----------+      |   |
  |  |                                          |                  |   |
  |  |                                   consolidate()             |   |
  |  |                                          |                  |   |
  |  |                                          v                  |   |
  |  |                               +----------------------+      |   |
  |  |                               | requirements_        |      |   |
  |  |                               | memory.md            |      |   |
  |  |                               | (trend analysis)     |      |   |
  |  |                               +----------------------+      |   |
  |  |                                                             |   |
  |  +-------------------------------------------------------------+   |
  +--------------------------------------------------------------------+
```

---

## Requirements Memory Trend Engine

```
  requirements_history.jsonl
  +--------+--------+--------+--------+--------+
  | Run 1  | Run 2  | Run 3  | Run 4  | Run 5  |  ...Run N
  | 03/10  | 03/11  | 03/12  | 03/12  | 03/13  |
  +---+----+---+----+---+----+---+----+---+----+
      |        |        |        |        |
      v        v        v        v        v
  +------------------------------------------------------+
  |              consolidate() -> Trend Analysis          |
  |                                                       |
  |  PAM-SUP-03:   PASS -> PASS -> FAIL -> FAIL -> FAIL  |
  |                                 ^                     |
  |                          REGRESSION detected          |
  |                          + 3 consecutive FAIL         |
  |                          = ALERT printed to CLI       |
  |                                                       |
  |  CHR-PATCH-03:  FAIL -> FAIL -> PASS -> PASS -> PASS |
  |                                  ^                    |
  |                          RECOVERY detected            |
  |                                                       |
  |  PAM-AUTH-03:   PASS -> PASS -> PASS -> PASS -> PASS |
  |                          = STABLE                     |
  |                                                       |
  |  MER-SPEC-02:   PASS -> FAIL -> PASS -> FAIL -> PASS |
  |                          = FLAPPING (3+ changes)      |
  +------------------------------------------------------+
                          |
                          v
  requirements_memory.md
  +------------------------------------------------------+
  |  ## Regressions     PAM-SUP-03 (PASS -> FAIL)        |
  |  ## Recoveries      CHR-PATCH-03 (FAIL -> PASS)      |
  |  ## Flapping        MER-SPEC-02 (changed 4x)         |
  |  ## Persistent FAIL (none)                            |
  |  ## Stable PASS     42 requirements                   |
  |  ## Timeline        last 10 runs grid                 |
  +------------------------------------------------------+
```

---

## Parallel Memory Systems

```
  +-------------------------------+     +-------------------------------+
  |    STEP CORRECTION MEMORY     |     |   REQUIREMENTS TREND MEMORY   |
  |    (existing system)          |     |   (new system)                |
  +-------------------------------+     +-------------------------------+
  |                               |     |                               |
  |  Tracks:                      |     |  Tracks:                      |
  |  Playwright navigation        |     |  Business requirement         |
  |  failures + what fixed them   |     |  PASS/FAIL trends over N runs |
  |                               |     |                               |
  |  Adapts:                      |     |  Adapts:                      |
  |  Next run auto-applies        |     |  Surfaces regressions,        |
  |  known corrections            |     |  recoveries, flapping after   |
  |  (networkidle, wait_500,      |     |  code changes                 |
  |   relogin, skip)              |     |                               |
  +-------------------------------+     +-------------------------------+
  |  Files:                       |     |  Files:                       |
  |  playwrightcli/feedback.md    |     |  playwrightcli/               |
  |  playwrightcli/memory.md      |     |    requirements_feedback.md   |
  |                               |     |    requirements_history.jsonl  |
  |                               |     |    requirements_memory.md      |
  +-------------------------------+     +-------------------------------+
```

---

## File Layout

```
  playwrightcli/
  |-- cli.py                       --verify flag, wiring
  |-- config.py                    portal URLs, creds
  |-- runner.py                    step retry engine
  |-- memory_manager.py            step correction memory
  |-- observer.py                  design observer (Claude Vision)
  |-- requirements_verifier.py     DOM assertions per page
  |-- requirements_memory.py       trend tracking across runs
  |-- feedback.md                  step correction log
  |-- memory.md                    step correction knowledge
  |-- requirements_feedback.md     verification run log
  |-- requirements_history.jsonl   structured run data
  |-- requirements_memory.md       trend analysis
  +-- flows/
  |   |-- base_flow.py             verify() + capture() methods
  |   |-- pam_flow.py              5 verify points
  |   |-- meredith_flow.py         3 verify points + deprecation checks
  |   |-- chrissy_flow.py          5 verify points
  |   |-- scope_flow.py            scope isolation + cert flow (standalone)
  |   |-- rbac_flow.py             RBAC cross-portal (standalone)
  |   |-- lifecycle_wizard_flow.py lifecycle wizard E2E (standalone, LC-WIZ-01..08)
  |   |-- layer2_wizard_flow.py    Layer 2 wizard E2E (standalone, L2-WIZ-01..09)
  |   +-- wizard_session_flow.py   multi-session persistence (standalone, WIZ-SESS-01..04)
  +-- fixtures/
      |-- seed.sql                 idempotent test data
      |-- signal_checker.py        standalone S3 signal scanner
      |-- artifact_checker.py      standalone S3 artifact checker
      +-- token_fetcher.py         standalone DB reader for reset tokens

  requirements_reports/            per-run reports
  cliRequirements.md               master checklist + docs
  cliRequirementsDiagram.md        this file
```

---

## Step-Level Flow Detail

```
  +-------------------------------------------------------------------+
  |  Example: chrissy::patches step                                    |
  |                                                                    |
  |  1. run_step("chrissy::patches", self._patches, ...)              |
  |     |                                                              |
  |     +-> self.goto("/patches")                                      |
  |     +-> self.assert_page_ok()        # no 500, no session expiry   |
  |     +-> self.wait_htmx()             # HTMX swap settles           |
  |     +-> page.wait_for_selector(...)  # table or empty-state        |
  |     |                                                              |
  |     +-> PASS / FAIL (with retry + correction loop)                 |
  |                                                                    |
  |  2. capture("patches")              # screenshot -> observer queue |
  |     |                                                              |
  |     +-> only if --observe active                                   |
  |                                                                    |
  |  3. verify("patches")              # DOM assertions on live page   |
  |     |                                                              |
  |     +-> only if --verify active                                    |
  |     +-> RequirementsVerifier.verify("chrissy::patches", page)      |
  |         |                                                          |
  |         +-> CHR-PATCH-01: Page loads without error       [PASS]    |
  |         +-> CHR-PATCH-02: Patch cards render             [PASS]    |
  |         +-> CHR-PATCH-03: "Mark Applied" action exists   [PASS]    |
  |         +-> CHR-PATCH-04: "Reject" action exists         [SKIP]    |
  |         +-> CHR-PATCH-05: Filter controls present        [FAIL]    |
  |         +-> CHR-PATCH-06: Patch content viewable         [PASS]    |
  |                                                                    |
  +-------------------------------------------------------------------+
```

---

## CLI Usage Matrix

```
  +--------------------------------------------+-------+--------+--------+
  | Command                                    | Steps | Design | Verify |
  +--------------------------------------------+-------+--------+--------+
  | playwrightcli --portal all                 |  yes  |   no   |   no   |
  | playwrightcli --portal all --observe       |  yes  |  yes   |   no   |
  | playwrightcli --portal all --verify        |  yes  |   no   |  yes   |
  | playwrightcli --portal all --observe --verify | yes |  yes   |  yes   |
  | playwrightcli --portal all --dry-run       | show  |   no   |   no   |
  | playwrightcli --portal all --verify --dry-run | show |  no   | show   |
  | playwrightcli --consolidate                |   no  |   no   |   no   |
  |   (consolidates both memory systems)       |       |        |        |
  +--------------------------------------------+-------+--------+--------+
```
