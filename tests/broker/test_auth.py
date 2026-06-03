"""Tests for request-token extraction."""

from __future__ import annotations

import pytest

from algotrading.broker.auth import extract_request_token


def test_extract_from_full_redirect_url() -> None:
    url = "https://example.com/redirect?action=login&status=success&request_token=abc123XYZ"
    assert extract_request_token(url) == "abc123XYZ"


def test_extract_from_url_with_extra_params() -> None:
    url = "https://app.local/cb?request_token=tok_42&type=login"
    assert extract_request_token(url) == "tok_42"


def test_accepts_bare_token() -> None:
    assert extract_request_token("  rawtoken123 ") == "rawtoken123"


def test_empty_input_raises() -> None:
    with pytest.raises(ValueError):
        extract_request_token("   ")


def test_url_without_request_token_raises() -> None:
    with pytest.raises(ValueError):
        extract_request_token("https://example.com/redirect?status=success")
