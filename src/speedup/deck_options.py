# Speedup - an Anki add-on derived from Speed Focus Mode
# Copyright (C) 2026 Speedup contributors
# Based on Speed Focus Mode, Copyright (C) 2017-2022 Aristotelis P. (Glutanimate)
# License: GNU AGPL v3 or later (see LICENSE)

"""Per-preset settings inside Anki's deck options screen."""

from __future__ import annotations

import json
from pathlib import Path

from aqt import gui_hooks
from aqt.deckoptions import DeckOptionsDialog, display_options_for_deck_id
from aqt.qt import QAction, QMenu, qconnect

from .config_manager import get_config
from .consts import PATH_WEB
from .stats.dialog import show_stats_for_deck

_WEB = Path(PATH_WEB)


def _load(name: str) -> str:
    return (_WEB / name).read_text(encoding="utf-8")


def on_deck_options_did_load(dialog: DeckOptionsDialog) -> None:
    if dialog.web is None:
        return
    html = _load("deck_options.html")
    script = _load("deck_options.js")
    script = script.replace("__GLOBAL_CONFIG__", json.dumps(get_config()))
    script = script.replace("__HTML__", json.dumps(html))
    dialog.web.eval(script)


def on_deck_browser_will_show_options_menu(menu: QMenu, deck_id: int) -> None:
    options_action = QAction("Speedup options…", menu)
    qconnect(options_action.triggered, lambda: display_options_for_deck_id(deck_id))
    menu.addAction(options_action)

    stats_action = QAction("Speedup statistics…", menu)
    qconnect(stats_action.triggered, lambda: show_stats_for_deck(deck_id))
    menu.addAction(stats_action)


def initialize_deck_options() -> None:
    gui_hooks.deck_options_did_load.append(on_deck_options_did_load)
    gui_hooks.deck_browser_will_show_options_menu.append(
        on_deck_browser_will_show_options_menu
    )
