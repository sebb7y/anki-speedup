# Speedup - an Anki add-on derived from Speed Focus Mode
# Copyright (C) 2026 Speedup contributors
# Based on Speed Focus Mode, Copyright (C) 2017-2022 Aristotelis P. (Glutanimate)
# License: GNU AGPL v3 or later (see LICENSE)

"""Small helper around QTimer for scheduling and cancelling card timers."""

from __future__ import annotations

from typing import Callable

from aqt import mw
from aqt.qt import QTimer


class TimerGroup:
    """A collection of single-shot timers that can be cleared together."""

    def __init__(self) -> None:
        self._timers: list[QTimer] = []

    def schedule(self, milliseconds: float, callback: Callable[[], None]) -> QTimer:
        timer = QTimer(mw)
        timer.setSingleShot(True)
        timer.timeout.connect(callback)
        timer.start(max(1, int(round(milliseconds))))
        self._timers.append(timer)
        return timer

    def clear(self) -> None:
        for timer in self._timers:
            timer.stop()
            timer.deleteLater()
        self._timers.clear()
