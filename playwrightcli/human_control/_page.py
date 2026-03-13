"""_page.py — HTML template for the human-control page.

render_page() returns a complete HTML document. No external dependencies.
The page polls GET /status every 1.5 s and reloads its content when
step_id changes, so it stays in sync as the harness advances.
"""
from __future__ import annotations


def render_page(
    step: str,
    guidance: str,
    portal: str,
    port: int,
    portal_url: str = "",
    step_id: int = 0,
) -> str:
    portal_label = portal.upper() if portal else "PORTAL"
    step_label = step or "Waiting for run to start…"
    guidance_text = guidance or "The harness has not started yet."
    portal_link = (
        f'<a href="{portal_url}" target="_blank" class="portal-link">{portal_url}</a>'
        if portal_url
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>certPortal · Human Control</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #0f1117;
      color: #e2e8f0;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
    }}

    .card {{
      background: #1a1d27;
      border: 1px solid #2d3148;
      border-radius: 12px;
      padding: 40px 48px;
      max-width: 640px;
      width: 100%;
      box-shadow: 0 8px 32px rgba(0,0,0,0.4);
    }}

    .badge {{
      display: inline-block;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      background: #2d3148;
      color: #818cf8;
      border-radius: 4px;
      padding: 3px 8px;
      margin-bottom: 20px;
    }}

    .step-name {{
      font-size: 22px;
      font-weight: 700;
      color: #f1f5f9;
      margin-bottom: 16px;
      font-family: "SF Mono", "Cascadia Code", "Fira Code", monospace;
      word-break: break-all;
    }}

    .guidance {{
      font-size: 15px;
      line-height: 1.65;
      color: #94a3b8;
      margin-bottom: 32px;
      padding: 16px;
      background: #12151f;
      border-left: 3px solid #818cf8;
      border-radius: 0 6px 6px 0;
    }}

    .portal-link {{
      display: block;
      margin-bottom: 24px;
      font-size: 13px;
      color: #60a5fa;
      text-decoration: none;
      word-break: break-all;
    }}
    .portal-link:hover {{ text-decoration: underline; }}

    .actions {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
    }}

    .btn {{
      flex: 1;
      min-width: 140px;
      padding: 14px 24px;
      border: none;
      border-radius: 8px;
      font-size: 15px;
      font-weight: 600;
      cursor: pointer;
      transition: opacity 0.15s, transform 0.1s;
    }}
    .btn:active {{ transform: scale(0.97); }}
    .btn:disabled {{ opacity: 0.4; cursor: not-allowed; }}

    .btn-advance {{
      background: #4f46e5;
      color: #fff;
    }}
    .btn-advance:hover:not(:disabled) {{ background: #4338ca; }}

    .btn-skip {{
      background: #1e2130;
      color: #94a3b8;
      border: 1px solid #2d3148;
    }}
    .btn-skip:hover:not(:disabled) {{ background: #252840; }}

    .status-bar {{
      margin-top: 24px;
      font-size: 12px;
      color: #475569;
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .dot {{
      width: 8px; height: 8px;
      border-radius: 50%;
      background: #22c55e;
      animation: pulse 2s infinite;
    }}
    @keyframes pulse {{
      0%, 100% {{ opacity: 1; }}
      50% {{ opacity: 0.3; }}
    }}
    .dot.waiting {{ background: #f59e0b; }}

    #feedback {{
      margin-top: 16px;
      font-size: 13px;
      color: #22c55e;
      min-height: 18px;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="badge">{portal_label} portal</div>

    <div class="step-name" id="step-name">{step_label}</div>

    <div class="guidance" id="guidance">{guidance_text}</div>

    {portal_link}

    <div class="actions">
      <button class="btn btn-advance" id="btn-advance" onclick="doAction('advance')">
        ✓ Done, advance
      </button>
      <button class="btn btn-skip" id="btn-skip" onclick="doAction('skip')">
        Skip step
      </button>
    </div>

    <div id="feedback"></div>

    <div class="status-bar">
      <span class="dot" id="dot"></span>
      <span id="status-text">Connected · polling for step updates</span>
    </div>
  </div>

  <script>
    let lastStepId = {step_id};
    let actionSent = false;

    async function doAction(action) {{
      if (actionSent) return;
      actionSent = true;

      document.getElementById('btn-advance').disabled = true;
      document.getElementById('btn-skip').disabled = true;
      document.getElementById('dot').className = 'dot waiting';

      const label = action === 'advance' ? 'Advancing…' : 'Skipping…';
      document.getElementById('feedback').textContent = label;
      document.getElementById('status-text').textContent = 'Waiting for next step…';

      try {{
        await fetch('/' + action, {{ method: 'POST' }});
      }} catch (e) {{
        document.getElementById('feedback').textContent = 'Error: ' + e;
        return;
      }}

      // Poll until step_id changes (next step is set)
      pollForNextStep();
    }}

    async function pollForNextStep() {{
      while (true) {{
        await sleep(800);
        try {{
          const r = await fetch('/status');
          if (!r.ok) continue;
          const data = await r.json();
          if (data.step_id !== lastStepId) {{
            lastStepId = data.step_id;
            applyStatus(data);
            actionSent = false;
            document.getElementById('btn-advance').disabled = false;
            document.getElementById('btn-skip').disabled = false;
            document.getElementById('dot').className = 'dot';
            document.getElementById('feedback').textContent = '';
            document.getElementById('status-text').textContent = 'Connected · polling for step updates';
            break;
          }}
        }} catch (e) {{}}
      }}
    }}

    function applyStatus(data) {{
      document.getElementById('step-name').textContent = data.step || 'Waiting…';
      document.getElementById('guidance').textContent = data.guidance || '';
    }}

    // Background poll to detect step changes (e.g. harness skipped internally)
    async function backgroundPoll() {{
      while (true) {{
        await sleep(1500);
        if (actionSent) continue;
        try {{
          const r = await fetch('/status');
          if (!r.ok) continue;
          const data = await r.json();
          if (data.step_id !== lastStepId) {{
            lastStepId = data.step_id;
            applyStatus(data);
          }}
        }} catch (e) {{}}
      }}
    }}

    function sleep(ms) {{ return new Promise(r => setTimeout(r, ms)); }}

    backgroundPoll();
  </script>
</body>
</html>"""
