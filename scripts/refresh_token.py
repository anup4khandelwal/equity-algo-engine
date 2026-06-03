#!/usr/bin/env python3
"""Refresh the daily Kite Connect access token.

The Kite access token expires every morning, and minting a new one requires a
browser login that redirects back with a short-lived ``request_token``. This
script automates as much as possible:

  1. Opens the Kite login URL in your browser.
  2. You log in; Kite redirects to your app's redirect URL with a
     ``request_token`` in the query string.
  3. You paste that redirect URL (or just the token) back here.
  4. We exchange it for an access token and store it locally (gitignored).

Run with:  uv run python scripts/refresh_token.py

No secret is ever printed to the terminal.
"""

from __future__ import annotations

import sys
import webbrowser
from datetime import datetime
from pathlib import Path

# Make `algotrading` (under src/) and `config` (repo root) importable when this
# script is run directly, since the project is managed as an app, not installed.
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from config.settings import get_settings  # noqa: E402

from algotrading.broker.auth import extract_request_token  # noqa: E402
from algotrading.broker.token_store import KiteToken, TokenStore  # noqa: E402


def main() -> int:
    settings = get_settings()

    from kiteconnect import KiteConnect

    kite = KiteConnect(api_key=settings.kite_api_key)
    login_url = kite.login_url()

    print("Opening the Kite login page in your browser...")
    print(f"If it doesn't open, visit:\n  {login_url}\n")
    try:
        webbrowser.open(login_url)
    except Exception:  # pragma: no cover - browser is best-effort
        pass

    print(
        "After logging in, copy the URL you were redirected to (it contains\n"
        "'request_token=...') and paste it below."
    )
    redirect = input("Redirect URL (or request_token): ").strip()

    try:
        request_token = extract_request_token(redirect)
    except ValueError as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        return 1

    print("\nExchanging request token for an access token...")
    data = kite.generate_session(request_token, api_secret=settings.kite_api_secret)

    token = KiteToken(
        access_token=data["access_token"],
        public_token=data.get("public_token"),
        user_id=data.get("user_id"),
        login_time=str(data.get("login_time", datetime.now().isoformat())),
    )

    store = TokenStore()
    store.save(token)

    print(f"\nAccess token saved to {store.path} (gitignored).")
    print(f"Logged in as: {token.user_id or 'unknown'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
