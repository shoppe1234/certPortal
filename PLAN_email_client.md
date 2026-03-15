# Plan: Email Client Integration for Meredith (Retailer) Portal

## Context

The Meredith (retailer) portal currently has no way to invite suppliers for EDI certification. Today, supplier accounts are manually seeded via database migrations. Retailers need a self-service flow to:
1. Submit supplier names + email addresses (individually or in bulk)
2. Send branded email invitations for certification
3. Track invite status (sent, accepted, declined, expired)
4. Communicate with suppliers via email threads with full visibility

**Approach**: Portal-link model — suppliers respond via web pages (no inbound email parsing). Invite acceptance lives on the Meredith portal as public routes. Bulk import supports both CSV paste and file upload.

---

## Step 1: Database Migration — `migrations/006_supplier_invites.sql`

Three new tables following existing idempotent DDL patterns:

**`supplier_invites`** — tracks each invited supplier
- `id` SERIAL PK, `retailer_slug`, `supplier_name`, `supplier_email`, `invite_token` (UNIQUE), `status` (CHECK: pending/sent/accepted/declined/expired), `invited_by` (username), `sent_at`, `responded_at`, `created_at`, `expires_at`
- Indexes on retailer_slug, status, token, email

**`email_threads`** — groups messages between retailer and supplier contact
- `id` SERIAL PK, `thread_id` (UNIQUE TEXT, UUID-based), `retailer_slug`, `supplier_email`, `supplier_name`, `subject`, `invite_id` (nullable FK to supplier_invites), `status` (active/archived), `created_at`, `updated_at`
- Indexes on retailer_slug, invite_id

**`email_messages`** — individual messages within a thread
- `id` SERIAL PK, `thread_id` (FK), `direction` (outbound/inbound), `sender`, `body_text`, `body_html`, `sent_at`, `read_at`, `delivery_status` (queued/sent/failed)
- Indexes on thread_id, sent_at

---

## Step 2: Extend Email Utils — `certportal/core/email_utils.py`

Refactor existing code and add new functions. Reuse existing SMTP env vars.

| Function | Purpose |
|----------|---------|
| `_get_smtp_config()` | Extract SMTP config from env (factored out of `send_reset_email`) |
| `send_email(to_addr, subject, body_text, body_html=None) -> bool` | Generic SMTP send (core function) |
| `send_reset_email(...)` | **Existing** — refactored to delegate to `send_email()` |
| `send_invite_email(to_addr, supplier_name, retailer_name, invite_link) -> bool` | Branded HTML invite with CTA button + 30-day expiry notice |
| `send_thread_reply_notification(to_addr, subject, body_text, reply_link) -> bool` | Notify supplier of new message with portal link |

All functions follow existing fail-safe pattern: return `bool`, never raise, log to stderr.

---

## Step 3: Meredith Portal Routes — `portals/meredith.py`

### Public Routes (on `app`, no auth required)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/invite/accept?token=...` | Render branded accept/decline page for supplier |
| POST | `/invite/respond` | Record supplier's accept/decline, update DB + thread |

### Protected Routes (on `router`, require admin/retailer role)

**Invite Management:**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/invites` | Invite management page (form + list) |
| POST | `/invites` | Create single invite, send email, create thread |
| POST | `/invites/bulk` | Parse CSV (paste or file upload), create invites in transaction |
| GET | `/invites/{invite_id}` | Single invite detail with timeline |
| POST | `/invites/{invite_id}/resend` | Resend invite email, reset token |

**Email Threads:**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/email` | Thread inbox — list all threads for retailer |
| GET | `/email/{thread_id}` | Thread detail — messages in chronological order, mark unread as read |
| POST | `/email/{thread_id}/reply` | Send reply, insert outbound message, email notification to supplier |

**HTMX Partials:**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/htmx/invite-list` | Refresh invite table body (30s polling) |
| GET | `/htmx/email-inbox` | Refresh inbox thread list |
| GET | `/htmx/thread-messages/{thread_id}` | Refresh messages in thread view |

### Invite Flow:
1. Retailer fills form (name + email) or uploads CSV → POST `/invites` or `/invites/bulk`
2. System generates `secrets.token_urlsafe(32)` token, INSERTs into `supplier_invites` + creates `email_thread` + first `email_message`
3. Sends branded invite email via `send_invite_email()`
4. Supplier clicks link → GET `/invite/accept?token=...` → sees accept/decline page
5. Supplier responds → POST `/invite/respond` → status updated, inbound message recorded in thread
6. Retailer sees updated status on `/invites` page + message in `/email/{thread_id}`

---

## Step 4: Templates

All extend `base.html`, use existing DM Sans font, Meredith color palette.

| Template | Description |
|----------|-------------|
| `meredith_invites.html` | Two-panel: invite form (single + bulk CSV/file) on top, data table below with status pills + HTMX polling |
| `meredith_email_inbox.html` | Card-based thread list (similar to PAM HITL queue), unread badge, last message preview |
| `meredith_email_thread.html` | Chat-bubble layout: outbound right (primary blue), inbound left (gray). Reply textarea at bottom |
| `_invite_row.html` | HTMX partial — single invite table row |
| `_invite_list.html` | HTMX partial — full invite table body |
| `_thread_card.html` | HTMX partial — single thread card for inbox |
| `_message_bubble.html` | HTMX partial — single message for thread view |
| `_email_inbox_list.html` | HTMX partial — full inbox list |

---

## Step 5: CSS — `static/css/meredith.css`

New classes following existing conventions:
- Invite status pills: `.invite-pending`, `.invite-sent`, `.invite-accepted`, `.invite-declined`, `.invite-expired`
- Thread cards: `.thread-card`, `.thread-preview`, `.unread-badge`
- Message bubbles: `.msg-bubble`, `.msg-outbound`, `.msg-inbound`, `.msg-meta`
- Reply form: `.reply-form`, `.reply-textarea`

---

## Step 6: Navigation + Dashboard Updates

- Add "Invites" and "Email" nav links to `{% block nav_links %}` in all 4 existing Meredith templates
- Add invite action card to `meredith_home.html` dashboard
- Add pending-invites and accepted counts to dashboard stats row

---

## Step 7: Tests — Suite J in `testing/suites/suite_j.py`

Register in `testing/certportal_jules_test.py` as `("SuiteJ — Supplier Invite & Email", suite_j)`.

| Test Category | Tests |
|---------------|-------|
| Email utils | `send_email` success/failure, `send_invite_email` MIME format, `send_thread_reply_notification` |
| Invite lifecycle | Token generation, status transitions, expiry validation, bulk CSV parsing, duplicate handling |
| Thread/messages | Thread auto-creation on invite, reply creates outbound message, updated_at refresh |
| Routes | Auth requirements (401/403), POST /invites, public /invite/accept, GET /email |

---

## Implementation Order

1. `migrations/006_supplier_invites.sql` — schema first
2. `certportal/core/email_utils.py` — extend with generic + invite functions
3. `portals/meredith.py` — public accept/decline routes
4. `portals/meredith.py` — invite management routes
5. `portals/meredith.py` — email thread routes + HTMX partials
6. Templates — all new `.html` files
7. `static/css/meredith.css` — new styles
8. Nav + dashboard updates to existing templates
9. `testing/suites/suite_j.py` — test suite

---

## Critical Files

| File | Action |
|------|--------|
| `migrations/006_supplier_invites.sql` | **CREATE** — new migration |
| `certportal/core/email_utils.py` | **MODIFY** — refactor + add functions |
| `portals/meredith.py` | **MODIFY** — add ~15 new routes |
| `templates/meredith_invites.html` | **CREATE** — invite management page |
| `templates/meredith_email_inbox.html` | **CREATE** — email inbox |
| `templates/meredith_email_thread.html` | **CREATE** — thread view |
| `templates/_invite_row.html` | **CREATE** — HTMX partial |
| `templates/_invite_list.html` | **CREATE** — HTMX partial |
| `templates/_thread_card.html` | **CREATE** — HTMX partial |
| `templates/_message_bubble.html` | **CREATE** — HTMX partial |
| `templates/_email_inbox_list.html` | **CREATE** — HTMX partial |
| `templates/meredith_home.html` | **MODIFY** — add invite card + nav |
| `templates/meredith_spec_setup.html` | **MODIFY** — add nav links |
| `templates/meredith_yaml_wizard.html` | **MODIFY** — add nav links |
| `templates/meredith_supplier_status.html` | **MODIFY** — add nav links |
| `static/css/meredith.css` | **MODIFY** — add new styles |
| `testing/suites/suite_j.py` | **CREATE** — test suite |
| `testing/certportal_jules_test.py` | **MODIFY** — register suite J |

## Verification

1. Apply migration: `psql $CERTPORTAL_DB_URL -f migrations/006_supplier_invites.sql`
2. Start Meredith: `python -m portals.meredith` (port 8001)
3. Login as `lowes_retailer` / `certportal_retailer`
4. Navigate to `/invites` — verify form renders, submit a test invite
5. Check email delivery (or verify in DB if SMTP not configured)
6. Visit `/invite/accept?token=<token>` — verify public accept page renders
7. Click Accept — verify DB status updates and thread message appears
8. Navigate to `/email` — verify inbox shows thread
9. Open thread, send a reply — verify message appears in chat view
10. Run tests: `python -m testing.certportal_jules_test` — verify Suite J passes
