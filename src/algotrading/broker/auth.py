"""Helpers for the Kite Connect login/token-exchange flow.

The interactive flow lives in ``scripts/refresh_token.py``; the pure, testable
pieces live here.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse


def extract_request_token(redirect: str) -> str:
    """Pull the ``request_token`` out of a Kite post-login redirect.

    Accepts either the full redirect URL (``https://.../?request_token=abc&...``)
    or the bare token string. Raises ``ValueError`` if no token can be found.
    """
    candidate = redirect.strip()
    if not candidate:
        raise ValueError("empty redirect input")

    parsed = urlparse(candidate)
    if parsed.query:
        tokens = parse_qs(parsed.query).get("request_token")
        if tokens and tokens[0]:
            return tokens[0]

    # Not a URL with the param — treat the input as the raw token, but reject
    # anything that still looks like a URL to avoid silently storing garbage.
    if parsed.scheme or "/" in candidate or "?" in candidate:
        raise ValueError("could not find 'request_token' in the provided redirect URL")
    return candidate
