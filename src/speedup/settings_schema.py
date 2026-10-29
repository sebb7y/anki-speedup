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

OVERLAY_POSITIONS: tuple[str, ...] = (
    "top-right",
    "top-left",
    "bottom-right",
    "bottom-left",
)

PERIODS: tuple[str, ...] = ("today", "all")


def _default_auto_action(action: str = "again") -> dict[str, Any]:
    return {"after": 0.0, "action": action}


def default_class_settings() -> dict[str, Any]:
    return {
        "question": {
            "alertAfter": 0.0,
            "revealAfter": 0.0,
            "autoAction": _default_auto_action("again"),
        },
        "answer": {
            "alertAfter": 0.0,
            "autoAction": _default_auto_action("good"),
        },
    }


def default_global_settings() -> dict[str, Any]:
    return {
        "enabled": True,
        "moreTime": {"showButton": False, "hotkey": "p"},
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
            "averagePeriod": "today",
            "overlayPosition": "top-right",
            "overlayFontSize": 12,
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


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_bool(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _as_number(value: Any, default: float = 0.0, minimum: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, number)


def _as_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return min(maximum, max(minimum, number))


def _as_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return min(maximum, max(minimum, number))


def _as_choice(value: Any, choices: tuple[str, ...], default: str) -> str:
    return value if value in choices else default


def _as_action(value: Any, default: str) -> str:
    return value if value in ACTIONS else default


def normalize_class_settings(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Return a complete, type-safe class settings dict."""
    raw = _as_dict(raw)
    question = _as_dict(raw.get("question"))
    answer = _as_dict(raw.get("answer"))
    question_action = _as_dict(question.get("autoAction"))
    answer_action = _as_dict(answer.get("autoAction"))

    return {
        "question": {
            "alertAfter": _as_number(question.get("alertAfter")),
            "revealAfter": _as_number(question.get("revealAfter")),
            "autoAction": {
                "after": _as_number(question_action.get("after")),
                "action": _as_action(question_action.get("action"), "again"),
            },
        },
        "answer": {
            "alertAfter": _as_number(answer.get("alertAfter")),
            "autoAction": {
                "after": _as_number(answer_action.get("after")),
                "action": _as_action(answer_action.get("action"), "good"),
            },
        },
    }


def normalize_global_settings(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Merge raw user config on top of the defaults and sanitize every value."""
    merged = deep_merge(default_global_settings(), _as_dict(raw))

    more_time = _as_dict(merged.get("moreTime"))
    grouping = _as_dict(merged.get("grouping"))
    ui = _as_dict(merged.get("ui"))
    analytics = _as_dict(merged.get("analytics"))
    adaptive = _as_dict(merged.get("adaptive"))
    defaults = _as_dict(merged.get("defaults"))

    hotkey = str(more_time.get("hotkey") or "p").strip() or "p"
    alert_sound = str(merged.get("alertSound") or "default").strip() or "default"

    return {
        "enabled": _as_bool(merged.get("enabled"), True),
        "moreTime": {
            "showButton": _as_bool(more_time.get("showButton"), False),
            "hotkey": hotkey,
        },
        "stopTimersWhenTyping": _as_bool(merged.get("stopTimersWhenTyping"), True),
        "suppressBuiltInAutoAdvance": _as_bool(merged.get("suppressBuiltInAutoAdvance"), True),
        "alertSound": alert_sound,
        "grouping": {
            "collapseNewLearning": _as_bool(grouping.get("collapseNewLearning"), False),
            "collapseReviewRelearning": _as_bool(grouping.get("collapseReviewRelearning"), False),
        },
        "defaults": {
            card_class: normalize_class_settings(defaults.get(card_class))
            for card_class in CARD_CLASSES
        },
        "ui": {
            "showCountdown": _as_bool(ui.get("showCountdown"), True),
            "showAverage": _as_bool(ui.get("showAverage"), False),
            "showDeckTotal": _as_bool(ui.get("showDeckTotal"), False),
            "showOverallTotal": _as_bool(ui.get("showOverallTotal"), False),
            "totalPeriod": _as_choice(ui.get("totalPeriod"), PERIODS, "today"),
            "averagePeriod": _as_choice(ui.get("averagePeriod"), PERIODS, "today"),
            "overlayPosition": _as_choice(
                ui.get("overlayPosition"), OVERLAY_POSITIONS, "top-right"
            ),
            "overlayFontSize": _as_int(ui.get("overlayFontSize"), 12, 8, 48),
        },
        "analytics": {
            "enabled": _as_bool(analytics.get("enabled"), False),
            "markSlowFast": _as_bool(analytics.get("markSlowFast"), False),
            "slowPercentile": _as_int(analytics.get("slowPercentile"), 75, 50, 99),
            "fastPercentile": _as_int(analytics.get("fastPercentile"), 25, 1, 50),
        },
        "adaptive": {
            "enabled": _as_bool(adaptive.get("enabled"), False),
            "factor": _as_float(adaptive.get("factor"), 0.97, 0.5, 1.0),
            "windowDays": _as_int(adaptive.get("windowDays"), 30, 1, 365),
            "floor": _as_number(adaptive.get("floor"), 1.0),
        },
    }


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
    base = normalize_class_settings(defaults.get(card_class))

    override = (deck_override or {}).get(card_class)
    merged = normalize_class_settings(deep_merge(base, override))

    # The global switch is a true master switch: a deck override may disable
    # timers for its preset, but it may not re-enable them globally.
    global_enabled = bool(global_config.get("enabled", True))
    deck_enabled = bool((deck_override or {}).get("enabled", True))
    merged["enabled"] = global_enabled and deck_enabled
    merged["cardClass"] = card_class
    return merged


def _after_values(settings: dict[str, Any]) -> list[float]:
    question = settings.get("question", {})
    answer = settings.get("answer", {})
    values = [
        question.get("alertAfter", 0.0),
        question.get("revealAfter", 0.0),
        question.get("autoAction", {}).get("after", 0.0),
        answer.get("alertAfter", 0.0),
        answer.get("autoAction", {}).get("after", 0.0),
    ]
    return [float(v or 0.0) for v in values]


def has_any_timer(settings: dict[str, Any]) -> bool:
    if not settings.get("enabled", True):
        return False
    return any(value > 0 for value in _after_values(settings))


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
            "autoAction": {"after": 0.0, "action": "again"},
        },
        "answer": {
            "alertAfter": 0.0,
            "autoAction": {"after": back_action, "action": "good"},
        },
    }


def apply_adaptive(
    settings: dict[str, Any],
    avg_front_s: float,
    avg_back_s: float,
    *,
    factor: float,
    floor: float,
) -> dict[str, Any]:
    """Replace enabled timers with values derived from recent averages."""
    result = normalize_class_settings(settings)
    total_s = (avg_front_s or 0.0) + (avg_back_s or 0.0)

    def target(avg: float) -> float:
        if avg <= 0:
            return 0.0
        return max(floor, round(avg * factor, 2))

    question = result["question"]
    answer = result["answer"]

    if question.get("revealAfter", 0) > 0 and avg_front_s > 0:
        question["revealAfter"] = target(avg_front_s)
    if question.get("alertAfter", 0) > 0 and avg_front_s > 0:
        question["alertAfter"] = max(floor, round(avg_front_s * factor * 0.8, 2))
    if question.get("autoAction", {}).get("after", 0) > 0 and total_s > 0:
        question["autoAction"]["after"] = target(total_s)
    if answer.get("alertAfter", 0) > 0 and avg_back_s > 0:
        answer["alertAfter"] = max(floor, round(avg_back_s * factor * 0.8, 2))
    if answer.get("autoAction", {}).get("after", 0) > 0 and avg_back_s > 0:
        answer["autoAction"]["after"] = target(avg_back_s)

    return result
