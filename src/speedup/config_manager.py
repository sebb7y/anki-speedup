# Speedup - an Anki add-on derived from Speed Focus Mode
# Copyright (C) 2026 Speedup contributors
# Based on Speed Focus Mode, Copyright (C) 2017-2022 Aristotelis P. (Glutanimate)
# License: GNU AGPL v3 or later (see LICENSE)

"""Global configuration handling and deck-config override access."""

from __future__ import annotations

from typing import Any, Callable

from aqt import mw

from .consts import CONFIG_NAMESPACE, MODULE_ADDON
from .settings_schema import deep_merge, default_global_settings

_config: dict[str, Any] = default_global_settings()

_listeners: list[Callable[[], None]] = []


def _normalize(raw: dict[str, Any] | None) -> dict[str, Any]:
    return deep_merge(default_global_settings(), raw or {})


def load_config() -> dict[str, Any]:
    global _config
    _config = _normalize(mw.addonManager.getConfig(MODULE_ADDON))
    return _config


def get_config() -> dict[str, Any]:
    return _config


def save_config(config: dict[str, Any]) -> None:
    global _config
    _config = _normalize(config)
    mw.addonManager.writeConfig(MODULE_ADDON, _config)


def add_config_listener(callback: Callable[[], None]) -> None:
    _listeners.append(callback)


def _on_config_updated(*_args: Any) -> None:
    load_config()
    for callback in _listeners:
        callback()


def initialize_config() -> None:
    load_config()
    mw.addonManager.setConfigUpdatedAction(MODULE_ADDON, _on_config_updated)


def get_deck_override(deck_id: int) -> dict[str, Any]:
    """Return this add-on's namespaced overrides for a deck's config preset."""
    if mw.col is None:
        return {}
    deck_config = mw.col.decks.config_dict_for_deck_id(deck_id)
    override = deck_config.get(CONFIG_NAMESPACE)
    if isinstance(override, dict):
        return override
    return {}


def get_deck_override_for_config(deck_config: dict[str, Any]) -> dict[str, Any]:
    override = deck_config.get(CONFIG_NAMESPACE)
    if isinstance(override, dict):
        return override
    return {}


def set_deck_override(deck_id: int, override: dict[str, Any]) -> None:
    """Persist namespaced overrides into a deck's config preset."""
    if mw.col is None:
        return
    deck_config = mw.col.decks.config_dict_for_deck_id(deck_id)
    if override:
        deck_config[CONFIG_NAMESPACE] = override
    else:
        deck_config.pop(CONFIG_NAMESPACE, None)
    mw.col.decks.update_config(deck_config)
