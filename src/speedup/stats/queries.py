# Speedup - an Anki add-on derived from Speed Focus Mode
# Copyright (C) 2026 Speedup contributors
# Based on Speed Focus Mode, Copyright (C) 2017-2022 Aristotelis P. (Glutanimate)
# License: GNU AGPL v3 or later (see LICENSE)

"""Read-only aggregations over Anki's revlog."""

from __future__ import annotations

import time
from collections.abc import Sequence

from aqt import mw


def _deck_ids(deck_id: int) -> list[int]:
    if mw.col is None:
        return []
    return [int(did) for did in mw.col.decks.deck_and_child_ids(deck_id)]


def _cutoff_ms(period: str) -> int:
    if period == "today" and mw.col is not None:
        return (mw.col.sched.day_cutoff - 86400) * 1000
    return 0


def _window_cutoff_ms(days: int | None) -> int:
    if not days or days <= 0:
        return 0
    return int((time.time() - days * 86400) * 1000)


def _deck_clause(deck_ids: Sequence[int]) -> str:
    placeholders = ",".join("?" * len(deck_ids))
    return f"cid IN (SELECT id FROM cards WHERE did IN ({placeholders}))"


def deck_average_ms(
    deck_id: int, *, period: str = "all", days: int | None = None
) -> float | None:
    deck_ids = _deck_ids(deck_id)
    if not deck_ids:
        return None
    cutoff = _window_cutoff_ms(days) if days else _cutoff_ms(period)
    sql = (
        "SELECT AVG(time) FROM revlog WHERE "
        + _deck_clause(deck_ids)
        + " AND id >= ?"
    )
    value = mw.col.db.scalar(sql, *deck_ids, cutoff)
    if value is None:
        return None
    return float(value)


def deck_total_ms(deck_id: int, *, period: str = "today") -> int:
    deck_ids = _deck_ids(deck_id)
    if not deck_ids:
        return 0
    cutoff = _cutoff_ms(period)
    sql = (
        "SELECT SUM(time) FROM revlog WHERE "
        + _deck_clause(deck_ids)
        + " AND id >= ?"
    )
    value = mw.col.db.scalar(sql, *deck_ids, cutoff)
    return int(value or 0)


def overall_total_ms(*, period: str = "today") -> int:
    cutoff = _cutoff_ms(period)
    value = mw.col.db.scalar("SELECT SUM(time) FROM revlog WHERE id >= ?", cutoff)
    return int(value or 0)


def card_average_map(
    deck_id: int, *, days: int | None = None
) -> dict[int, float]:
    """Map of cid -> average total answer time (ms) for a deck."""
    deck_ids = _deck_ids(deck_id)
    if not deck_ids:
        return {}
    cutoff = _window_cutoff_ms(days)
    sql = (
        "SELECT cid, AVG(time) AS avg_time FROM revlog WHERE "
        + _deck_clause(deck_ids)
        + " AND id >= ? GROUP BY cid"
    )
    rows = mw.col.db.all(sql, *deck_ids, cutoff)
    return {int(row[0]): float(row[1]) for row in rows if row[1] is not None}


def percentile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(fraction * (len(ordered) - 1)))))
    return float(ordered[index])
