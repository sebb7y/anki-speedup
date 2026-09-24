# Speedup - an Anki add-on derived from Speed Focus Mode
# Copyright (C) 2026 Speedup contributors
# Based on Speed Focus Mode, Copyright (C) 2017-2022 Aristotelis P. (Glutanimate)
# License: GNU AGPL v3 or later (see LICENSE)

"""Opt-in local storage of per-card front/back times.

Anki's revlog only stores total answer time, so the front/back split and
per-card history are kept in a small SQLite database inside ``user_files``.
This data is local to the machine and is not synced.
"""

from __future__ import annotations

import os
import sqlite3
import time
from typing import Any

from ..consts import PATH_USERFILES

_DB_PATH = os.path.join(PATH_USERFILES, "speedup.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS card_times (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cid INTEGER NOT NULL,
    did INTEGER NOT NULL,
    ts INTEGER NOT NULL,
    front_ms INTEGER NOT NULL,
    back_ms INTEGER NOT NULL,
    total_ms INTEGER NOT NULL,
    ease INTEGER NOT NULL,
    card_type INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_card_times_cid ON card_times (cid);
CREATE INDEX IF NOT EXISTS idx_card_times_did ON card_times (did);
CREATE INDEX IF NOT EXISTS idx_card_times_ts ON card_times (ts);
"""


def _connect() -> sqlite3.Connection:
    os.makedirs(PATH_USERFILES, exist_ok=True)
    connection = sqlite3.connect(_DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.executescript(_SCHEMA)
    return connection


def record(
    *,
    cid: int,
    did: int,
    front_ms: int,
    back_ms: int,
    ease: int,
    card_type: int,
) -> None:
    total_ms = max(0, front_ms) + max(0, back_ms)
    with _connect() as connection:
        connection.execute(
            "INSERT INTO card_times (cid, did, ts, front_ms, back_ms, total_ms, ease, card_type)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                int(cid),
                int(did),
                int(time.time()),
                int(front_ms),
                int(back_ms),
                int(total_ms),
                int(ease),
                int(card_type),
            ),
        )


def _since(days: int | None) -> int:
    if not days or days <= 0:
        return 0
    return int(time.time()) - days * 86400


def card_averages(cid: int, days: int | None = None) -> tuple[float, float] | None:
    """Average (front_ms, back_ms) for a single card, or None if no data."""
    with _connect() as connection:
        row = connection.execute(
            "SELECT AVG(front_ms) AS front, AVG(back_ms) AS back, COUNT(*) AS n"
            " FROM card_times WHERE cid = ? AND ts >= ?",
            (int(cid), _since(days)),
        ).fetchone()
    if row is None or not row["n"]:
        return None
    return float(row["front"] or 0.0), float(row["back"] or 0.0)


def deck_averages(did: int, days: int | None = None) -> tuple[float, float] | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT AVG(front_ms) AS front, AVG(back_ms) AS back, COUNT(*) AS n"
            " FROM card_times WHERE did = ? AND ts >= ?",
            (int(did), _since(days)),
        ).fetchone()
    if row is None or not row["n"]:
        return None
    return float(row["front"] or 0.0), float(row["back"] or 0.0)


def card_totals(did: int, days: int | None = None) -> dict[int, int]:
    """Map of cid -> average total time (ms) for a deck."""
    with _connect() as connection:
        rows = connection.execute(
            "SELECT cid, AVG(total_ms) AS total FROM card_times"
            " WHERE did = ? AND ts >= ? GROUP BY cid",
            (int(did), _since(days)),
        ).fetchall()
    return {int(row["cid"]): int(row["total"] or 0) for row in rows}


def card_stats(did: int, days: int | None = None) -> list[dict[str, Any]]:
    """Per-card average front/back/total times for a deck."""
    with _connect() as connection:
        rows = connection.execute(
            "SELECT cid, AVG(front_ms) AS front, AVG(back_ms) AS back,"
            " AVG(total_ms) AS total, COUNT(*) AS n FROM card_times"
            " WHERE did = ? AND ts >= ? GROUP BY cid ORDER BY total DESC",
            (int(did), _since(days)),
        ).fetchall()
    return [
        {
            "cid": int(row["cid"]),
            "front": int(row["front"] or 0),
            "back": int(row["back"] or 0),
            "total": int(row["total"] or 0),
            "count": int(row["n"] or 0),
        }
        for row in rows
    ]


def distribution(did: int, days: int | None = None) -> dict[str, list[int]]:
    """Front/back/total answer times (ms) for charts."""
    with _connect() as connection:
        rows = connection.execute(
            "SELECT front_ms, back_ms, total_ms FROM card_times"
            " WHERE did = ? AND ts >= ?",
            (int(did), _since(days)),
        ).fetchall()
    return {
        "front": [int(row["front_ms"]) for row in rows],
        "back": [int(row["back_ms"]) for row in rows],
        "total": [int(row["total_ms"]) for row in rows],
    }


def stats() -> dict[str, Any]:
    with _connect() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS n, AVG(total_ms) AS avg FROM card_times"
        ).fetchone()
    return {"count": int(row["n"] or 0), "average_ms": float(row["avg"] or 0.0)}


def clear() -> None:
    with _connect() as connection:
        connection.execute("DELETE FROM card_times")
