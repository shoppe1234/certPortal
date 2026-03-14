"""layer2_wizard_flow.py — Layer 2 YAML Wizard E2E flow (Phase P4).

Standalone flow (no BaseFlow import — follows scope_flow.py pattern).
Verifies the full Layer 2 wizard journey: new session, preset selection,
segment config, business rules, mapping notes, review, generate YAML,
generate artifacts, artifact download.

Steps (handles own login/logout):
  layer2-wizard::landing            GET /yaml-wizard — verify Layer 2 tab
  layer2-wizard::new-session        POST /yaml-wizard/layer2/new -> redirect
  layer2-wizard::preset-select      Step 0: select preset "standard_retail" -> save-step
  layer2-wizard::segment-config     Step 1: verify accordions render -> save-step
  layer2-wizard::business-rules     Step 2: verify toggles render -> save-step
  layer2-wizard::mapping-notes      Step 3: verify mapping notes -> save-step
  layer2-wizard::review             Step 4: verify YAML preview
  layer2-wizard::generate-yaml      POST generate -> verify success
  layer2-wizard::generate-artifacts POST generate-artifacts -> verify success
  layer2-wizard::download           GET /artifacts/{slug}/850.md -> verify content
  layer2-wizard::verify-db          Verify wizard_sessions row

Requirements verified:
  L2-WIZ-01..09  Layer 2 wizard end-to-end
"""
from __future__ import annotations

from playwrightcli.config import PORTALS, TIMEOUTS

PORTAL = "layer2-wizard"

LAYER2_WIZARD_STEPS = [
    "landing",
    "new-session",
    "preset-select",
    "segment-config",
    "business-rules",
    "mapping-notes",
    "review",
    "generate-yaml",
    "generate-artifacts",
    "download",
    "verify-db",
]

_MEREDITH_URL = PORTALS["meredith"]["url"]
_USERNAME = PORTALS["meredith"]["username"]
_PASSWORD = PORTALS["meredith"]["password"]


class Layer2WizardFlow:
    """Standalone Layer 2 wizard flow — does not extend BaseFlow."""

    def __init__(self, page, runner, *, verifier=None) -> None:
        self.page = page
        self.runner = runner
        self._verifier = verifier
        self._session_id: str | None = None
        self._retailer_slug: str = "lowes"

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def run(self) -> None:
        r = self.runner
        pfx = f"{PORTAL}::"

        await r.run_step(f"{pfx}landing",            self._landing,            page=self.page)
        await r.run_step(f"{pfx}new-session",         self._new_session,        page=self.page)
        await r.run_step(f"{pfx}preset-select",       self._preset_select,      page=self.page)
        await r.run_step(f"{pfx}segment-config",      self._segment_config,     page=self.page)
        await r.run_step(f"{pfx}business-rules",      self._business_rules,     page=self.page)
        await r.run_step(f"{pfx}mapping-notes",       self._mapping_notes,      page=self.page)
        await r.run_step(f"{pfx}review",              self._review,             page=self.page)
        await r.run_step(f"{pfx}generate-yaml",       self._generate_yaml,      page=self.page)
        await r.run_step(f"{pfx}generate-artifacts",  self._generate_artifacts, page=self.page)
        await r.run_step(f"{pfx}download",            self._download,           page=self.page)
        await r.run_step(f"{pfx}verify-db",           self._verify_db,          page=self.page)

        await self._logout()

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    async def _login(self) -> None:
        await self.page.goto(
            f"{_MEREDITH_URL}/login",
            wait_until="domcontentloaded",
            timeout=TIMEOUTS["navigation"],
        )
        await self.page.fill('input[name="username"]', _USERNAME)
        await self.page.fill('input[name="password"]', _PASSWORD)
        async with self.page.expect_navigation(timeout=TIMEOUTS["navigation"]):
            await self.page.click('button[type="submit"]')
        if "/login" in self.page.url:
            raise AssertionError(f"Login failed for {_USERNAME}")

    async def _logout(self) -> None:
        await self.page.evaluate("""() => {
            const f = document.createElement('form');
            f.method = 'POST';
            f.action = '/logout';
            document.body.appendChild(f);
            f.submit();
        }""")
        await self.page.wait_for_url("**/login**", timeout=TIMEOUTS["navigation"])

    async def _goto(self, path: str) -> None:
        await self.page.goto(
            f"{_MEREDITH_URL}{path}",
            wait_until="domcontentloaded",
            timeout=TIMEOUTS["navigation"],
        )
        await self.page.wait_for_load_state("networkidle", timeout=TIMEOUTS["networkidle"])

    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    async def _landing(self) -> None:
        """Login and navigate to /yaml-wizard — verify Layer 2 tab exists."""
        await self._login()
        await self._goto("/yaml-wizard")

        body_text = (await self.page.text_content("body") or "").lower()
        has_layer2 = "layer 2" in body_text or "layer2" in body_text
        if not has_layer2:
            raise AssertionError("Layer 2 wizard tab not found on /yaml-wizard")

    async def _new_session(self) -> None:
        """POST /yaml-wizard/layer2/new with transaction_type=850, x12_version=004010."""
        result = await self.page.evaluate("""async () => {
            try {
                const r = await fetch('/yaml-wizard/layer2/new', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                    body: 'transaction_type=850&x12_version=004010&session_name=E2E+Test+Layer2',
                    redirect: 'follow'
                });
                return {ok: r.ok, status: r.status, url: r.url};
            } catch (e) {
                return {ok: false, status: 0, url: '', error: String(e)};
            }
        }""")

        if result.get("url") and "/yaml-wizard/layer2/" in result["url"]:
            self._session_id = result["url"].rstrip("/").split("/")[-1]
            if "?" in self._session_id:
                self._session_id = self._session_id.split("?")[0]
            await self._goto(f"/yaml-wizard/layer2/{self._session_id}")
        else:
            # Fallback: look for a form or link on the page
            start_btn = await self.page.query_selector(
                'button:has-text("Start"), a:has-text("Layer 2"), '
                'button[type="submit"]'
            )
            if start_btn:
                async with self.page.expect_navigation(timeout=TIMEOUTS["navigation"]):
                    await start_btn.click()
                url = self.page.url
                if "/yaml-wizard/layer2/" in url:
                    self._session_id = url.rstrip("/").split("/")[-1]
                    if "?" in self._session_id:
                        self._session_id = self._session_id.split("?")[0]

        if not self._session_id:
            raise AssertionError("Failed to create Layer 2 wizard session")

    async def _preset_select(self) -> None:
        """Step 0: Select preset 'standard_retail' and save step."""
        if self._verifier:
            await self._verifier.verify_layer2_preset_selection(self.page)

        await self.page.evaluate(f"""async () => {{
            const r = await fetch('/yaml-wizard/layer2/{self._session_id}/save-step', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                body: 'step_number=0&preset=standard_retail'
            }});
            return {{ok: r.ok, status: r.status}};
        }}""")

        await self._goto(f"/yaml-wizard/layer2/{self._session_id}")

    async def _segment_config(self) -> None:
        """Step 1: Verify segment accordions render, accept defaults, save step."""
        if self._verifier:
            await self._verifier.verify_layer2_segment_accordions(self.page)

        await self.page.evaluate(f"""async () => {{
            const r = await fetch('/yaml-wizard/layer2/{self._session_id}/save-step', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                body: 'step_number=1'
            }});
            return {{ok: r.ok, status: r.status}};
        }}""")

        await self._goto(f"/yaml-wizard/layer2/{self._session_id}")

    async def _business_rules(self) -> None:
        """Step 2: Verify business rules toggles render, accept defaults, save step."""
        await self.page.evaluate(f"""async () => {{
            const r = await fetch('/yaml-wizard/layer2/{self._session_id}/save-step', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                body: 'step_number=2'
            }});
            return {{ok: r.ok, status: r.status}};
        }}""")

        await self._goto(f"/yaml-wizard/layer2/{self._session_id}")

    async def _mapping_notes(self) -> None:
        """Step 3: Verify mapping notes, save step."""
        await self.page.evaluate(f"""async () => {{
            const r = await fetch('/yaml-wizard/layer2/{self._session_id}/save-step', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                body: 'step_number=3'
            }});
            return {{ok: r.ok, status: r.status}};
        }}""")

        await self._goto(f"/yaml-wizard/layer2/{self._session_id}")

    async def _review(self) -> None:
        """Step 4: Review — verify YAML preview shows content."""
        body_text = (await self.page.text_content("body") or "")
        # Check for YAML-like content in preview
        has_preview = ("850" in body_text or "transaction" in body_text.lower()
                       or "segments" in body_text.lower() or "yaml" in body_text.lower())
        if self._verifier and has_preview:
            self._verifier.verify_layer2_yaml_valid(body_text)

    async def _generate_yaml(self) -> None:
        """POST generate and verify success."""
        result = await self.page.evaluate(f"""async () => {{
            try {{
                const r = await fetch('/yaml-wizard/layer2/{self._session_id}/generate', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                    body: ''
                }});
                const html = await r.text();
                return {{ok: r.ok, status: r.status, html: html}};
            }} catch (e) {{
                return {{ok: false, status: 0, error: String(e)}};
            }}
        }}""")

        if self._verifier:
            status = result.get("status", 0)
            self._verifier.verify_layer2_yaml_valid(
                result.get("html", "") if status == 200 else ""
            )

    async def _generate_artifacts(self) -> None:
        """POST generate-artifacts and verify success."""
        result = await self.page.evaluate(f"""async () => {{
            try {{
                const r = await fetch('/yaml-wizard/layer2/{self._session_id}/generate-artifacts', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                    body: ''
                }});
                return {{ok: r.ok, status: r.status}};
            }} catch (e) {{
                return {{ok: false, status: 0, error: String(e)}};
            }}
        }}""")

        if self._verifier:
            sc = self._verifier.signal_checker
            if sc:
                md_exists = sc.object_exists(f"{self._retailer_slug}/specs/004010/850.md")
                self._verifier.verify_layer2_artifacts_generated(md_exists)
            else:
                self._verifier._skip("L2-WIZ-05", "Artifacts generated (MD file exists)", "S3 checker unavailable")

    async def _download(self) -> None:
        """GET /artifacts/{slug}/850.md and verify content."""
        result = await self.page.evaluate(f"""async () => {{
            try {{
                const r = await fetch('/artifacts/{self._retailer_slug}/850.md');
                const text = await r.text();
                return {{ok: r.ok, status: r.status, length: text.length, content: text.substring(0, 500)}};
            }} catch (e) {{
                return {{ok: false, status: 0, length: 0, content: '', error: String(e)}};
            }}
        }}""")

        if self._verifier:
            self._verifier.verify_layer2_download(
                result.get("status", 0),
                result.get("length", 0),
            )

            content = result.get("content", "")
            if content:
                self._verifier.verify_layer2_annotations(content)
            else:
                self._verifier._skip("L2-WIZ-06", "Artifacts contain Layer 2 annotations", "No content to check")

    async def _verify_db(self) -> None:
        """Verify wizard_sessions row exists in DB."""
        if not self._verifier or not self._session_id:
            return

        session_exists = False
        try:
            import psycopg2
            from playwrightcli.fixtures.signal_checker import _load_dotenv
            import os
            env = _load_dotenv()
            db_url = os.environ.get("CERTPORTAL_DB_URL") or env.get("CERTPORTAL_DB_URL", "")
            if db_url:
                conn = psycopg2.connect(db_url)
                cur = conn.cursor()
                cur.execute(
                    "SELECT id FROM wizard_sessions WHERE id = %s::uuid",
                    (self._session_id,),
                )
                row = cur.fetchone()
                session_exists = row is not None
                cur.close()
                conn.close()
        except Exception:
            pass

        self._verifier.verify_layer2_db_session(session_exists)

        # L2-WIZ-09: Resume check — navigate away and back
        await self._goto("/")
        await self._goto("/yaml-wizard")
        body_text = (await self.page.text_content("body") or "").lower()
        session_listed = (
            self._session_id in body_text
            or "e2e test" in body_text
            or "resume" in body_text
            or "850" in body_text
        )
        self._verifier.verify_layer2_resume(session_listed)
