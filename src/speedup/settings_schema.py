# Speedup - an Anki add-on derived from Speed Focus Mode
# Copyright (C) 2026 Speedup contributors
# Based on Speed Focus Mode, Copyright (C) 2017-2022 Aristotelis P. (Glutanimate)
# License: GNU AGPL v3 or later (see LICENSE)

"""Pure settings logic: card classes, defaults, merging and recommendations.

This module intentionally has no Anki imports so it can be unit tested in
isolation.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

CARD_CLASSES: tuple[str, ...] = ("new", "learning", "review", "relearning")

CARD_TYPE_TO_CLASS: dict[int, str] = {
    0: "new",
    1: "learning",
    2: "review",
    3: "relearning",
}

ACTIONS: tuple[str, ...] = ("again", "hard", "good", "easy", "bury")

ACTION_LABELS: dict[str, str] = {
    "again": "Rate Again",
    "hard": "Rate Hard",
    "good": "Rate Good",
    "easy": "Rate Easy",
    "bury": "Bury Card",
}

EASE_FOR_ACTION: dict[str, int] = {
    "again": 1,
    "hard": 2,
    "good": 3,
    "easy": 4,
}


def _default_auto_action(*, skip_answer: bool = False) -> dict[str, Any]:
    return {"after": 0.0, "action": "again", "skipAnswer": skip_answer}


def default_class_settings() -> dict[str, Any]:
    return {
        "question": {
            "alertAfter": 0.0,
            "revealAfter": 0.0,
            "autoAction": _default_auto_action(skip_answer=False),
        },
        "answer": {
            "alertAfter": 0.0,
            "autoAction": _default_auto_action(),
        },
    }


def default_global_settings() -> dict[str, Any]:
    return {
        "enabled": True,
        "moreTime": {"showButton": True, "hotkey": "p"},
        "stopTimersWhenTyping": True,
        "suppressBuiltInAutoAdvance": True,
        "alertSound": "default",
        "grouping": {
            "collapseNewLearning": False,
            "collapseReviewRelearning": False,
        },
        "defaults": {card_class: default_class_settings() for card_class in CARD_CLASSES},
        "ui": {
            "showCountdown": True,
            "showAverage": False,
            "showDeckTotal": False,
            "showOverallTotal": False,
            "totalPeriod": "today",
        },
        "analytics": {
            "enabled": False,
            "markSlowFast": False,
            "slowPercentile": 75,
            "fastPercentile": 25,
        },
        "adaptive": {
            "enabled": False,
            "factor": 0.97,
            "windowDays": 30,
            "floor": 1.0,
        },
    }


def deep_merge(base: dict[str, Any], override: dict[str, Any] | None) -> dict[str, Any]:
    """Recursively merge ``override`` on top of a copy of ``base``."""
    result = deepcopy(base)
    if not override:
        return result
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def card_class_for(card_type: int, grouping: dict[str, Any] | None = None) -> str:
    """Map an Anki card type to a (possibly collapsed) settings class."""
    card_class = CARD_TYPE_TO_CLASS.get(int(card_type), "review")
    grouping = grouping or {}
    if card_class == "learning" and grouping.get("collapseNewLearning"):
        return "new"
    if card_class == "relearning" and grouping.get("collapseReviewRelearning"):
        return "review"
    return card_class


def effective_settings(
    global_config: dict[str, Any],
    deck_override: dict[str, Any] | None,
    card_type: int,
) -> dict[str, Any]:
    """Resolve the settings for a card type from global defaults + deck overrides."""
    grouping = global_config.get("grouping", {})
    card_class = card_class_for(card_type, grouping)

    defaults = global_config.get("defaults", {})
    base = defaults.get(card_class) or default_class_settings()

    override = (deck_override or {}).get(card_class)
    merged = deep_merge(base, override)

    enabled = (deck_override or {}).get("enabled", global_config.get("enabled", True))
    merged["enabled"] = bool(enabled)
    merged["cardClass"] = card_class
    return merged


def _after_values(settings: dict[str, Any]) -> list[float]:
    values = [
        settings.get("question", {}).get("alertAfter", 0.0),
        settings.get("question", {}).get("revealAfter", 0.0),
        settings.get("question", {}).get("autoAction", {}).get("after", 0.0),
        settings.get("answer", {}).get("alertAfter", 0.0),
        settings.get("answer", {}).get("autoAction", {}).get("after", 0.0),
    ]
    return [float(v or 0.0) for v in values]


def has_any_timer(settings: dict[str, Any]) -> bool:
    if not settings.get("enabled", True):
        return False
    return any(value > 0 for value in _after_values(settings))


def scale_times(settings: dict[str, Any], factor: float, floor: float = 0.0) -> dict[str, Any]:
    """Return settings with every ``after`` value multiplied and floored."""
    scaled = deepcopy(settings)

    def scale(value: Any) -> float:
        value = float(value or 0.0)
        if value <= 0:
            return 0.0
        return max(floor, round(value * factor, 2))

    scaled["question"]["alertAfter"] = scale(scaled["question"].get("alertAfter", 0.0))
    scaled["question"]["revealAfter"] = scale(scaled["question"].get("revealAfter", 0.0))
    scaled["question"]["autoAction"]["after"] = scale(
        scaled["question"].get("autoAction", {}).get("after", 0.0)
    )
    scaled["answer"]["alertAfter"] = scale(scaled["answer"].get("alertAfter", 0.0))
    scaled["answer"]["autoAction"]["after"] = scale(
        scaled["answer"].get("autoAction", {}).get("after", 0.0)
    )
    return scaled


def recommend_settings(
    avg_front: float,
    avg_back: float,
    *,
    factor: float = 1.0,
    alert_lead: float = 0.0,
    floor: float = 0.5,
) -> dict[str, Any]:
    """Suggest question/answer timings from average front/back times (seconds)."""
    reveal = max(floor, round(avg_front * factor, 1)) if avg_front > 0 else 0.0
    back_action = max(floor, round(avg_back * factor, 1)) if avg_back > 0 else 0.0
    alert = 0.0
    if reveal > 0 and alert_lead > 0:
        alert = max(0.0, round(reveal - alert_lead, 1))
    return {
        "question": {
            "alertAfter": alert,
            "revealAfter": reveal,
            "autoAction": {"after": 0.0, "action": "again", "skipAnswer": False},
        },
        "answer": {
            "alertAfter": 0.0,
            "autoAction": {"after": back_action, "action": "good"},
        },
    }
