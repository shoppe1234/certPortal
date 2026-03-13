# cliObserver — Real-Time Design Observer for playwrightcli

## What This Is

A concurrent design analysis system that runs alongside the existing Playwright E2E flows.
While Playwright navigates each portal (PAM, Meredith, Chrissy), a second asyncio task
captures full-page screenshots in real-time and sends them to Claude Vision API for
incremental design review. The observer sees the *sequence* of rendered states — not
isolated snapshots — so it can reason about cross-page consistency, navigation continuity,
HTMX partial render timing, and visual language coherence across the entire portal session.

Activated via: `python -m playwrightcli --portal all --observe`

---

## Architecture

```
asyncio event loop (single process, two concurrent tasks)
  |
  +-- Task A: Playwright Flow (producer)
  |     pam::login -> capture() -> queue.put(frame)
  |     pam::retailers -> capture() -> queue.put(frame)
  |     pam::hitl-queue -> capture() -> queue.put(frame)
  |     ...
  |
  +-- Task B: DesignObserver (consumer)
        queue.get() -> save PNG to screenshots/{portal}/{step}.png
                    -> send to Claude Vision API (asyncio.to_thread)
                    -> accumulate rolling context (last 3 analyses per portal)
                    -> print one-line summary to stdout
                    -> write design_reviews/design_review_{portal}_{ts}.md
```

**Key property:** The observer never blocks the Playwright flows. Screenshots are pushed
to an `asyncio.Queue`; the observer consumes them concurrently. If the API is slow, frames
queue up. If the API is unavailable, screenshots still save to disk.

---

## Files Changed

| File | Change | Purpose |
|------|--------|---------|
| `playwrightcli/observer.py` | **NEW** | `ObserverFrame`, `DesignObserver` classes, `DESIGN_REVIEW_SYSTEM` prompt, report writer |
| `playwrightcli/flows/base_flow.py` | Modified | Added `observer_queue` param to `__init__`, added `capture(step)` method |
| `playwrightcli/flows/pam_flow.py` | Modified | Added `await self.capture()` after each step (5 capture points) |
| `playwrightcli/flows/meredith_flow.py` | Modified | Added `await self.capture()` after each step (3 capture points) |
| `playwrightcli/flows/chrissy_flow.py` | Modified | Added `await self.capture()` after each step (5 capture points) |
| `playwrightcli/cli.py` | Modified | Added `--observe` flag, `_run_observed()` function, observer lifecycle management |
| `requirements.txt` | Modified | Added `anthropic>=0.39` |

---

## Capture Points (13 Total)

### PAM (Admin) — 5 frames
| Step | URL | What It Captures |
|------|-----|-----------------|
| `login` | `/` (post-auth redirect) | Dashboard: KPI row, agent grid, nav bar |
| `retailers` | `/retailers` | Retailer management table or empty state |
| `suppliers` | `/suppliers` | Supplier management table or empty state |
| `hitl-queue` | `/hitl-queue` | Human-in-the-loop approval queue (may be empty) |
| `monica-memory` | `/monica-memory` | Monica orchestrator memory log with pagination |

### Meredith (Retailer) — 3 frames
| Step | URL | What It Captures |
|------|-----|-----------------|
| `login` | `/` (post-auth redirect) | Home: stats row, action cards, onboarding banner |
| `spec-setup` | `/spec-setup` | Spec setup wizard: accordion steps, path tabs |
| `supplier-status` | `/supplier-status` | Supplier certification status table |

### Chrissy (Supplier) — 5 frames
| Step | URL | What It Captures |
|------|-----|-----------------|
| `login` | `/` (post-auth redirect) | Home: cert badge, progress bar, gate cards, quick links |
| `scenarios` | `/scenarios` | Test scenario cards with pass/fail/partial status |
| `errors` | `/errors` | Error groups with expandable detail cards |
| `patches` | `/patches` | Patch suggestion cards (HTMX-swapped, needs networkidle) |
| `certification` | `/certification` | Certification status page |

---

## Observer Analysis Framework

The Claude Vision system prompt (`DESIGN_REVIEW_SYSTEM`) evaluates each frame against
six categories:

1. **Visual Hierarchy & Typography** — font scale, weight contrast, WCAG AA contrast ratios,
   monospace vs sans-serif appropriateness
2. **Spacing & Layout** — 4/8px grid consistency, whitespace balance, responsive readiness
3. **Color System** — semantic consistency (success/warn/error), contrast against backgrounds,
   brand color overuse
4. **Component Quality** — button touch targets (44x44px min), table headers, card
   shadow/border/padding regularity, badge legibility
5. **Tailwind CSS Migration Path** — map custom CSS to utility equivalents, identify where
   Tailwind tokens would enforce consistency
6. **Modern SaaS Best Practices** — purposeful density per role, progressive disclosure,
   focus indicators, screen reader landmarks

The observer accumulates **rolling context**: each API call includes the last 3 analyses
for that portal, so Claude sees continuity across pages and can flag inconsistencies between
the dashboard and subpages (e.g., nav link active state, footer positioning, heading scale).

---

## Current Portal CSS Landscape

Understanding what the observer is evaluating:

### PAM — `static/css/pam.css`
- **Theme:** Dark industrial. Bloomberg terminal meets SaaS ops dashboard.
- **Palette:** `#0a0e1a` base, `#00ff88` active, `#ffaa00` warn, `#ff4455` error
- **Fonts:** IBM Plex Mono (primary), IBM Plex Sans (body)
- **Radius:** 4px flat. No shadows.
- **Design tokens:** 18 CSS custom properties on `:root`

### Meredith — `static/css/meredith.css`
- **Theme:** Clean enterprise SaaS. Notion meets Linear.
- **Palette:** `#f8f9fc` base, `#4f6ef7` primary, `#22c55e` success
- **Fonts:** DM Sans
- **Radius:** 8px cards, 4px buttons. Box shadows on surfaces.
- **Design tokens:** 15 CSS custom properties on `:root`

### Chrissy — `static/css/chrissy.css`
- **Theme:** Warm, friendly, task-completion focused. Approachable.
- **Palette:** `#fffbf7` base, `#f59e0b` primary, `#22c55e` success
- **Fonts:** Plus Jakarta Sans
- **Radius:** 12px cards, 8px small, 20px pill buttons. Gradient accents.
- **Design tokens:** 17 CSS custom properties on `:root`

---

## Known Design Issues to Watch For

These are areas the observer is expected to surface based on static CSS analysis.
The live observer will confirm or refute these with actual rendered evidence.

### PAM
- **Contrast risk:** `--color-text-dim: #6a8aa8` on `--color-base: #0a0e1a` — likely fails
  WCAG AA (4.5:1 for normal text). Monospace at 10-12px compounds the problem.
- **Touch targets:** `.btn-xs` is `padding: 2px 8px` — well below 44x44px minimum.
  `.btn-sm` at `padding: 4px 10px` is also undersized.
- **KPI values:** 28px monospace (`IBM Plex Mono`) for KPI numbers is visually heavy.
  Sans-serif or tabular-nums would be more readable at this size.
- **No shadows:** The flat dark theme relies entirely on 1px borders (`--color-border`)
  for depth. Works for data density but creates visual monotony across many sections.
- **Memory log grid:** `.memory-entry` uses a 5-column grid with fixed 170px / 90px / 30px
  columns — will break or truncate on viewports below ~900px.

### Meredith
- **Inconsistent radius:** Cards use `8px`, gate pills use `12px`, form inputs use `4px`.
  A single Tailwind `rounded-lg` / `rounded-md` / `rounded-sm` scale would unify this.
- **Hardcoded hover color:** `.btn-primary:hover { background: #3d5ce8; }` — not derived
  from `--color-primary`. Should be a CSS variable or Tailwind `hover:bg-indigo-600`.
- **Shadow stacking:** `.stat-card` and `.action-card` both use `--shadow` but nav uses
  `--shadow` too — three shadow layers visible simultaneously at viewport top.
- **`.th-hint`:** A table header hint class at `font-size: 10px; font-weight: 400` —
  may be invisible on some displays.

### Chrissy
- **Amber-on-white contrast:** `--color-primary: #f59e0b` as text on `--color-base: #fffbf7`
  fails WCAG AA for normal text (contrast ratio ~2.5:1). The CSS compensates with
  `--color-primary-dark: #d97706` in some places but not all.
- **Radius inconsistency:** 12px cards, 8px small cards, 20px pill buttons, 4px xs buttons,
  10px badges — five distinct radius values with no clear hierarchy.
- **Gradient overuse:** `.cert-badge` and `.progress-fill` both use `linear-gradient(135deg / 90deg)`
  with `#f59e0b` to `#f97316`. The angle difference (135 vs 90) creates subtle visual discord.
- **Button weight variance:** `.btn` at `font-weight: 700` + `border-radius: 20px` is visually
  dominant. Combined with `transform: translateY(-1px)` on hover, this is more playful than
  the rest of the portal's calm aesthetic.

### Cross-Portal
- **No shared design tokens:** Each portal defines its own `:root` variables independently.
  There is no base CSS layer or shared token file. A Tailwind `tailwind.config.js` with
  portal-specific theme extensions would enforce consistency where it matters (spacing,
  font scale, semantic colors) while allowing palette divergence.
- **Font loading:** All three portals reference Google Fonts (`IBM Plex`, `DM Sans`,
  `Plus Jakarta Sans`) but the CSS files don't include `@import` or `<link>` — font loading
  must be in `templates/base.html`. If fonts fail to load, all three portals fall back to
  `system-ui` with noticeably different rendering.
- **Login page not captured:** The `capture("login")` call happens *after* successful login
  (i.e., on the dashboard redirect). The login form itself is never screenshotted. This is a
  gap — the login page is the first impression and should be reviewed.

---

## Areas for Improvement

### 1. Add Login Page Capture (Pre-Auth)

**Current:** `capture("login")` fires after `self.login()` succeeds, so it captures the
dashboard, not the login form.

**Improvement:** Add a capture in `BaseFlow.login()` *before* filling credentials:
```python
async def login(self) -> None:
    await self.page.goto(f"{self.base_url}/login", ...)
    await self.capture("login-form")  # <-- capture the login page itself
    await self.page.fill(...)
```

**Impact:** The observer would see 3 additional frames (one per portal) showing the
unauthenticated login form — important for first-impression design review.

---

### 2. Capture After Failed Steps

**Current:** `capture()` is called unconditionally after `run_step()`, even if the step
failed. A failed step may leave the page in an error state, redirect to `/login`, or show
a 500 page — the screenshot captures whatever is on screen.

**Improvement:** Make capture conditional on step success:
```python
ok = await r.run_step(f"{pfx}retailers", self._retailers, ...)
if ok:
    await self.capture("retailers")
```

Alternatively, capture *both* on failure (as evidence) with a tagged name:
```python
if not ok:
    await self.capture("retailers__FAIL")
```

**Impact:** Failure screenshots become valuable diagnostic artifacts. Success-only captures
keep the design review clean. Supporting both gives the observer richer context.

---

### 3. Viewport-Variant Captures

**Current:** All screenshots are taken at the browser's default viewport size (Playwright
default: 1280x720).

**Improvement:** Add a `--viewport` flag or take multiple captures at key breakpoints:
```python
for width in [1280, 768, 375]:
    await self.page.set_viewport_size({"width": width, "height": 900})
    await self.capture(f"{step}_{width}px")
```

**Impact:** The observer could evaluate responsive behavior — critical for identifying
PAM's fixed-column grid layouts that will break on tablets, and Chrissy's pill buttons
that may overflow on mobile.

---

### 4. DOM + CSS Extraction Alongside Screenshots

**Current:** The observer sends only PNG screenshots to Claude Vision.

**Improvement:** Extract computed styles and DOM structure at each capture point:
```python
css_snapshot = await self.page.evaluate("""() => {
    const el = document.querySelector('.main-content');
    return JSON.stringify(getComputedStyle(el), null, 2);
}""")
```

Send this alongside the image so Claude can reference exact CSS values rather than
estimating from the visual. This makes the Tailwind migration path concrete — Claude
can say "replace `font-size: 12px; letter-spacing: 0.5px` with `text-xs tracking-wide`"
with confidence.

**Impact:** Moves analysis from "this looks like it might be 12px" to "this is exactly
12px with 0.5px letter-spacing, which maps to Tailwind `text-xs tracking-wide`."

---

### 5. Bidirectional Observer (Decision Feedback Loop)

**Current:** The observer is read-only — it consumes frames and writes reports, but
cannot influence the Playwright flow.

**Improvement:** Add a response queue so the observer can request follow-up actions:
```python
# Observer sees clipped content:
await response_queue.put({
    "action": "scroll_and_capture",
    "selector": ".data-table",
    "reason": "Table rows are clipped at viewport bottom"
})

# Flow checks response queue between steps:
while not response_queue.empty():
    directive = response_queue.get_nowait()
    if directive["action"] == "scroll_and_capture":
        await self.page.evaluate(f"document.querySelector('{directive[\"selector\"]}').scrollIntoView()")
        await self.capture(f"{step}__followup")
```

**Impact:** The observer becomes an active participant — it can request scroll positions,
hover states, expanded accordions, or mobile viewport captures based on what it sees.
This is the path toward autonomous design auditing.

---

### 6. Diff-Based Review Across Runs

**Current:** Each `--observe` run produces independent reports. There is no comparison
between runs.

**Improvement:** Store a manifest (`design_reviews/manifest.json`) mapping portal+step
to the most recent screenshot hash. On subsequent runs, compute image diff (pixel-level
or perceptual hash) and only send changed frames to the API. Include the previous
analysis in the prompt with a note: "This page changed since last review."

**Impact:** Efficient for iterative CSS refinement — after implementing Tailwind migration
changes, re-run `--observe` and only the visually changed pages are re-analyzed. Saves
API costs and focuses review on what actually changed.

---

### 7. Tailwind Migration Scaffold Generator

**Current:** The observer's analysis includes Tailwind utility class suggestions in prose.

**Improvement:** Add a `--generate-tailwind` post-processing step that parses the design
review reports and produces:
- A `tailwind.config.js` with custom theme tokens derived from each portal's CSS variables
- A mapping file (`css_to_tailwind_map.json`) linking each custom CSS class to its
  Tailwind equivalent

```json
{
  "pam": {
    ".kpi-value": "font-mono text-3xl font-bold",
    ".btn-primary": "bg-emerald-400 text-black border border-emerald-400",
    ".gate-pending": "inline-block px-2 py-0.5 rounded-sm font-mono text-[10px] font-bold uppercase tracking-wide"
  }
}
```

**Impact:** Converts the observer's qualitative analysis into actionable migration artifacts
that can be directly applied to the Jinja2 templates.

---

### 8. CDP Screencast Mode (True Third Process)

**Current:** Architecture B (asyncio producer-consumer) — observer lives in the same
Python process as Playwright.

**Improvement:** Architecture A — use Chrome DevTools Protocol screencast for a truly
independent observer process:
```python
# In cli.py, expose CDP:
cdp = await ctx.new_cdp_session(page)
await cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 60, "maxWidth": 1280})

# Separate process connects to CDP WebSocket:
cdp.on("Page.screencastFrame", lambda params: observer_queue.put(params))
```

**Impact:** The observer becomes a completely independent process that can:
- Be started/stopped independently of the Playwright flows
- Observe any Chromium session, not just the playwrightcli flows
- Run against external sites (competitor portals, design references) for comparison
- Continue observing during long HTMX polling or WebSocket-driven updates

---

### 9. Anthropic Client Instantiation per Frame

**Current:** `_analyze_frame()` creates a new `anthropic.Anthropic()` client on every
frame:
```python
async def _analyze_frame(self, frame):
    client = anthropic.Anthropic()  # new client per frame
```

**Improvement:** Create the client once in `__init__` and reuse:
```python
def __init__(self, queue, *, use_api=True):
    ...
    if self._use_api:
        import anthropic
        self._client = anthropic.Anthropic()
```

**Impact:** Avoids repeated client initialization overhead (connection pooling, config
parsing) across 13 frames. Minor but clean.

---

### 10. Screenshot-Only Mode (No API)

**Current:** When `ANTHROPIC_API_KEY` is not set, the observer captures screenshots but
skips analysis. However, there is no way to explicitly request screenshot-only mode when
the key *is* set.

**Improvement:** Add `--screenshot-only` flag:
```python
parser.add_argument("--screenshot-only", action="store_true",
    help="Capture screenshots without Claude Vision analysis")
```

Pass `use_api=False` to `DesignObserver` when set.

**Impact:** Useful for CI pipelines where you want screenshot artifacts for manual review
or external tools without API costs. Also useful for capturing baseline screenshots before
starting a redesign.

---

## Output Locations

| Artifact | Path | When Created |
|----------|------|-------------|
| Screenshots | `screenshots/{portal}/{step}.png` | Every `--observe` run |
| Design reviews | `design_reviews/design_review_{portal}_{timestamp}.md` | When API key is set |
| Feedback log | `playwrightcli/feedback.md` | On step failures (existing behavior) |
| Memory | `playwrightcli/memory.md` | On `--consolidate` (existing behavior) |

---

## Usage

```bash
# Full observe run — headed browser + real-time Claude Vision analysis
python -m playwrightcli --portal all --observe

# Single portal, headless, observe
python -m playwrightcli --portal pam --headless --observe

# Screenshots only (no API calls) — set no ANTHROPIC_API_KEY
unset ANTHROPIC_API_KEY
python -m playwrightcli --portal all --observe

# Standard E2E run (no observer, original behavior)
python -m playwrightcli --portal all
```

## Prerequisites

```bash
pip install anthropic>=0.39
export ANTHROPIC_API_KEY=sk-ant-...
```
