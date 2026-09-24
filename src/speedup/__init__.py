# Speedup - an Anki add-on derived from Speed Focus Mode
# Copyright (C) 2026 Speedup contributors
# Based on Speed Focus Mode, Copyright (C) 2017-2022 Aristotelis P. (Glutanimate)
# License: GNU AGPL v3 or later (see LICENSE)

"""Module-level entry point for Speedup."""

from __future__ import annotations

from aqt import gui_hooks, mw
from aqt.qt import QAction, qconnect

from .config_manager import initialize_config
from .consts import MODULE_ADDON
from .deck_options import initialize_deck_options
from .options_dialog import show_options_dialog
from .reviewer import initialize_reviewer
from .stats.dialog import initialize_stats

_initialized = False


def _add_tools_menu() -> None:
    action = QAction("Speedup options…", mw)
    qconnect(action.triggered, show_options_dialog)
    mw.form.menuTools.addAction(action)


def initialize_addon() -> None:
    global _initialized
    if _initialized:
        return

    initialize_config()
    mw.addonManager.setConfigAction(MODULE_ADDON, show_options_dialog)
    initialize_deck_options()
    initialize_reviewer()
    initialize_stats()
    _add_tools_menu()

    _initialized = True


gui_hooks.profile_did_open.append(initialize_addon)
