# Speedup - an Anki add-on derived from Speed Focus Mode
# Copyright (C) 2026 Speedup contributors
# Based on Speed Focus Mode, Copyright (C) 2017-2022 Aristotelis P. (Glutanimate)
# License: GNU AGPL v3 or later (see LICENSE)

"""Module-level entry point for Speedup."""

from __future__ import annotations

from aqt import gui_hooks, mw
from aqt.qt import QAction, QMenu, qconnect

from .config_manager import initialize_config
from .consts import MODULE_ADDON
from .deck_options import initialize_deck_options
from .options_dialog import show_options_dialog
from .reviewer import initialize_reviewer
from .stats.dialog import show_stats_for_current_deck

_initialized = False


def _add_tools_menu() -> None:
    """One Speedup submenu instead of several top-level Tools entries."""
    menu = QMenu("Speedup", mw)

    options_action = QAction("Options…", menu)
    qconnect(options_action.triggered, show_options_dialog)
    menu.addAction(options_action)

    stats_action = QAction("Statistics…", menu)
    qconnect(stats_action.triggered, show_stats_for_current_deck)
    menu.addAction(stats_action)

    mw.form.menuTools.addMenu(menu)


def initialize_addon() -> None:
    global _initialized
    if _initialized:
        return

    initialize_config()
    mw.addonManager.setConfigAction(MODULE_ADDON, show_options_dialog)
    initialize_deck_options()
    initialize_reviewer()
    _add_tools_menu()

    _initialized = True


gui_hooks.profile_did_open.append(initialize_addon)
