"""Tests for date-window chunking used by the backfill."""

from __future__ import annotations

from datetime import date

import pytest

from algotrading.data.backfill import date_chunks


def test_single_window_when_range_fits() -> None:
    chunks = date_chunks(date(2026, 1, 1), date(2026, 1, 10), chunk_days=60)
    assert chunks == [(date(2026, 1, 1), date(2026, 1, 10))]


def test_splits_into_inclusive_windows() -> None:
    chunks = date_chunks(date(2026, 1, 1), date(2026, 1, 5), chunk_days=2)
    assert chunks == [
        (date(2026, 1, 1), date(2026, 1, 2)),
        (date(2026, 1, 3), date(2026, 1, 4)),
        (date(2026, 1, 5), date(2026, 1, 5)),
    ]


def test_windows_are_contiguous_and_cover_the_range() -> None:
    chunks = date_chunks(date(2026, 1, 1), date(2026, 3, 31), chunk_days=60)
    assert chunks[0][0] == date(2026, 1, 1)
    assert chunks[-1][1] == date(2026, 3, 31)
    # No gaps and no overlaps between consecutive windows.
    for (_, prev_end), (next_start, _) in zip(chunks, chunks[1:], strict=False):
        assert (next_start - prev_end).days == 1


def test_same_day_range() -> None:
    assert date_chunks(date(2026, 1, 1), date(2026, 1, 1), 60) == [
        (date(2026, 1, 1), date(2026, 1, 1))
    ]


def test_invalid_chunk_days_raises() -> None:
    with pytest.raises(ValueError):
        date_chunks(date(2026, 1, 1), date(2026, 1, 2), 0)


def test_end_before_start_raises() -> None:
    with pytest.raises(ValueError):
        date_chunks(date(2026, 1, 2), date(2026, 1, 1), 60)
