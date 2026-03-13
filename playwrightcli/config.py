"""Portal URLs, dev credentials, and timeouts.

Credentials are copied directly from certportal/core/auth.py _DEV_USERS comments.
This file is the ONLY connection between playwrightcli/ and certPortal configuration.
No imports from certportal/ are allowed — this module must stand alone.
"""

PORTALS: dict[str, dict] = {
    "pam": {
        "url": "http://localhost:8000",
        "username": "pam_admin",
        "password": "certportal_admin",
        "role": "admin",
    },
    "meredith": {
        "url": "http://localhost:8001",
        "username": "lowes_retailer",
        "password": "certportal_retailer",
        "role": "retailer",
    },
    "chrissy": {
        "url": "http://localhost:8002",
        "username": "acme_supplier",
        "password": "certportal_supplier",
        "role": "supplier",
    },
}

TIMEOUTS: dict[str, int] = {
    "navigation": 30_000,   # ms — page.goto / wait_for_url
    "element": 10_000,      # ms — wait_for_selector
    "networkidle": 15_000,  # ms — wait_for_load_state('networkidle')
    "preflight": 5,         # seconds — urllib preflight check
}

MAX_RETRIES = 3
