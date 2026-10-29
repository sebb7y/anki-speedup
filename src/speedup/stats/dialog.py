# Speedup - an Anki add-on derived from Speed Focus Mode
# Copyright (C) 2026 Speedup contributors
# Based on Speed Focus Mode, Copyright (C) 2017-2022 Aristotelis P. (Glutanimate)
# License: GNU AGPL v3 or later (see LICENSE)

"""Statistics and analytics dialog."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from aqt import mw
from aqt.qt import QDialog, QVBoxLayout, QWidget
from aqt.utils import disable_help_button, restoreGeom, saveGeom, tooltip
from aqt.webview import AnkiWebView

from ..config_manager import (
    get_config,
    get_deck_override,
    save_config,
    set_deck_override,
)
from ..consts import PATH_WEB
from ..settings_schema import CARD_CLASSES, deep_merge, recommend_settings
from . import queries, store

TITLE = "SpeedupStats"
WINDOW_DAYS = 30


class StatsDialog(QDialog):
    def __init__(self, deck_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent or mw)
        self.deck_id = int(deck_id)
        self.setWindowTitle("Speedup statistics")
        disable_help_button(self)
        restoreGeom(self, TITLE, default_size=(780, 720))

        self.web = AnkiWebView(parent=self)
        self.web.set_bridge_command(self._on_bridge, self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)
        self._render()

    def _collect(self) -> dict[str, Any]:
        deck = mw.col.decks.get(self.deck_id) if mw.col is not None else None
        averages = store.deck_averages(self.deck_id, WINDOW_DAYS)
        avg_front = averages[0] if averages else None
        avg_back = averages[1] if averages else None
        cards = store.card_stats(self.deck_id, WINDOW_DAYS)
        totals = [card["total"] for card in cards]
        recommendation = None
        if averages is not None:
            front, back = averages
            recommendation = recommend_settings(front / 1000.0, back / 1000.0)
        return {
            "deckId": self.deck_id,
            "deckName": (deck or {}).get("name", "Deck"),
            "avgFrontMs": avg_front,
            "avgBackMs": avg_back,
            "avgTotalMs": queries.deck_average_ms(self.deck_id, period="all"),
            "recommendation": recommendation,
            "cards": cards,
            "distribution": store.distribution(self.deck_id, WINDOW_DAYS),
            "slowThresholdMs": queries.percentile(totals, 0.75) if totals else None,
            "fastThresholdMs": queries.percentile(totals, 0.25) if totals else None,
            "analyticsEnabled": bool(get_config().get("analytics", {}).get("enabled")),
            "windowDays": WINDOW_DAYS,
        }

    def _render(self) -> None:
        data = self._collect()
        html = (Path(PATH_WEB) / "charts.html").read_text(encoding="utf-8")
        payload = json.dumps(data).replace("<", "\\u003c")
        html = html.replace("__DATA__", payload)
        self.web.stdHtml(html)

    def _on_bridge(self, url: Any) -> None:
        if not isinstance(url, str):
            return
        if url.startswith("speedup-apply:"):
            payload = json.loads(url.split(":", 1)[1])
            self._apply(payload)
        elif url == "speedup-enable-analytics":
            self._enable_analytics()

    def _enable_analytics(self) -> None:
        config = deepcopy(get_config())
        analytics = dict(config.get("analytics", {}))
        analytics["enabled"] = True
        config["analytics"] = analytics
        save_config(config)
        tooltip("Analytics enabled. Review a few cards to collect data.")
        self._render()

    def _apply(self, recommendation: dict[str, Any]) -> None:
        question = recommendation.get("question", {})
        answer_action = recommendation.get("answer", {}).get("autoAction", {})
        patch = {
            "question": {
                "alertAfter": question.get("alertAfter", 0.0),
                "revealAfter": question.get("revealAfter", 0.0),
            },
            "answer": {
                "autoAction": {
                    "after": answer_action.get("after", 0.0),
                    "action": answer_action.get("action", "good"),
                }
            },
        }
        override = get_deck_override(self.deck_id)
        for card_class in CARD_CLASSES:
            override[card_class] = deep_merge(override.get(card_class, {}), patch)
        set_deck_override(self.deck_id, override)
        tooltip("Applied recommended timings.")
        self._render()

    def accept(self) -> None:
        saveGeom(self, TITLE)
        super().accept()

    def reject(self) -> None:
        saveGeom(self, TITLE)
        super().reject()


def show_stats_for_deck(deck_id: int) -> None:
    StatsDialog(deck_id).exec()


def show_stats_for_current_deck() -> None:
    if mw.col is None:
        return
    deck = mw.col.decks.current()
    if deck:
        show_stats_for_deck(deck["id"])
    else:
        tooltip("Open a deck first.")
