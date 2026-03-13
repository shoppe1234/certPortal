# certPortal Playwright Memory

<!-- Read at the start of every run. Rewritten by --consolidate. Hand-editable. -->
<!-- Step names: <portal>::<step>  or  all::<pattern> -->

## Shared Patterns
- all::login: POST /token redirects to / on success; ?error=... means bad credentials — check config.py.
- all::htmx: HTMX partials need wait_for_load_state('networkidle') after page load trigger.
  Correction: networkidle

## Portal-Specific Patterns
- pam::hitl-queue: '#hitl-table' is absent when the queue is empty — this is expected.
  Correction: skip — assert any page structure (h1/h2/main) instead of the table element.
- chrissy::patches: Patch list renders via HTMX swap after initial page load.
  Correction: networkidle — wait for networkidle before asserting patch list presence.
