# Master Task List — Deferred Discussion

**Date:** 2026-03-13
**Status:** PIN — to be addressed in a future session

---

## Context

We want to create a master task list `.md` file that walks a user from start to finish across all three certPortal portals.

**Personas covered:** Supplier · Retailer · Admin

**Scope of each persona's section:**
- Login instructions (step-by-step)
- Every available function with instructions on how to perform it
- Known limitations for each function
- Sequence numbers on every step (to drive Playwright storyboard + screenshot narration)

**Intended uses:**
1. Internal testing / QA checklist
2. Foundation for a user manual
3. Storyboard for Playwright CLI screenshot + narration automation

---

## Proposed Prompt (Draft)

> Review all portal route definitions (`portals/pam.py`, `portals/meredith.py`, `portals/chrissy.py`), all `.md` files, the Playwright flow files in `playwrightcli/flows/`, and `playwrightcli/fixtures/seed.sql`. Then generate a master task list `TASK_LIST.md` structured as follows:
>
> - Three top-level sections: **Admin (PAM)**, **Retailer (Meredith)**, **Supplier (Chrissy)**
> - Within each section: numbered steps (hierarchical: `1.0`, `1.1`, `1.1.1`) covering every function available to that persona
> - For each step include:
>   - Sequence number
>   - Step title
>   - Detailed instruction (what to click, what to fill in, what to expect)
>   - Expected result / success criteria
>   - Known limitations or constraints
>   - `[SCREENSHOT]` marker for Playwright storyboard checkpoints
>   - `[NARRATION]` caption (imperative voice: "Log in as a supplier. The dashboard appears.")
> - Error paths as sub-steps under the relevant happy-path step (e.g., `1.1.1` happy path → `1.1.2` wrong password → `1.1.3` account locked behavior)
> - A `[FUTURE]` tag on any step that covers deferred/not-yet-implemented functionality
> - An appendix section: **Account Bootstrap** — admin steps to create supplier and retailer accounts before those personas can log in
> - No detail is too small.

---

## Open Questions (Must Be Answered Before Writing the Document)

These questions were identified during the 2026-03-13 session and need answers to shape the final document correctly.

### Q1 — Audience Sophistication
Are end users EDI-literate (familiar with X12 transactions, 850/855/856 terminology) or business users who need plain-language explanations? This determines how much jargon is explained vs. assumed.

### Q2 — Sequence Numbering Scheme
- **Flat:** `1, 2, 3...` across all portals
- **Hierarchical:** `1.0 Admin, 1.1 Login, 1.2 Dashboard... 2.0 Retailer...`

Hierarchical maps cleanly to Playwright step IDs. Flat is easier to reference in conversation.

### Q3 — Happy Path Only vs. Error Paths
Error paths (wrong password, out-of-order gate → 409, rejected patch, scope violation → 403) are critical for QA but significantly expand the document. Options:
- Include as sub-steps under each happy-path step
- Separate dedicated "Error Scenarios" section
- Omit for v1 and add in a later pass

### Q4 — Account Creation Bootstrap
There is no self-registration. An admin must create all supplier and retailer accounts via PAM `/register`. Should the task list:
- Show admin creating each account as the *first step of each persona's journey*?
- Assume accounts pre-exist and start each section at login?

### Q5 — Limitation Type Distinction
Some limitations are **permanent by design** (e.g., supplier cannot certify — admin only) and some are **temporary TODOs** (no rate limiting, no audit log UI). Should both types be flagged in the same document, or separated so TODO items become a distinct roadmap/appendix section?

### Q6 — Playwright Narration Voice
Which voice for storyboard captions?
- **First-person user:** *"I log in as a supplier and navigate to my patch list."*
- **Third-person observer:** *"The supplier logs in and the system displays the patch list."*
- **Imperative/instructional:** *"Log in as a supplier. The patch list appears."* ← current preference implied

### Q7 — Screenshot Checkpoint Granularity
- Every step = a potential screenshot checkpoint, OR
- Only milestone moments (login, dashboard view, gate completion, certification badge)?

### Q8 — Deferred Features
Should Step #9 (Monica escalation), React frontend note, and other deferred items appear as `[FUTURE]` placeholders in the document, or be excluded to keep it focused on current functionality?

---

## Reference Files

| File | Purpose |
|------|---------|
| `portals/pam.py` | All PAM routes (admin, 19 routes) |
| `portals/meredith.py` | All Meredith routes (retailer, 14 routes) |
| `portals/chrissy.py` | All Chrissy routes (supplier, 13 routes) |
| `playwrightcli/flows/pam_flow.py` | Existing E2E steps for PAM |
| `playwrightcli/flows/meredith_flow.py` | Existing E2E steps for Meredith |
| `playwrightcli/flows/chrissy_flow.py` | Existing E2E steps for Chrissy |
| `playwrightcli/flows/scope_flow.py` | Scope isolation + certification steps |
| `playwrightcli/flows/rbac_flow.py` | RBAC cross-portal enforcement steps |
| `playwrightcli/fixtures/seed.sql` | Test users + seed data |
| `TODO.md` | Project backlog (see entry added 2026-03-13) |
| `DECISIONS.md` | ADR-001 through ADR-031 — architectural decisions |
| `cliRequirements.md` | Requirement IDs and definitions |
