# Speedup - an Anki add-on derived from Speed Focus Mode
# Copyright (C) 2026 Speedup contributors
# Based on Speed Focus Mode, Copyright (C) 2017-2022 Aristotelis P. (Glutanimate)
# License: GNU AGPL v3 or later (see LICENSE)

"""Reviewer timing engine and bottom-bar UI."""

from __future__ import annotations

import json
import os
import time
from copy import deepcopy
from dataclasses import dataclass, field
from functools import partial
from typing import Any, Callable

from anki.cards import Card
from aqt import gui_hooks, mw
from aqt.reviewer import Reviewer
from aqt.sound import av_player
from aqt.utils import tooltip

from .config_manager import (
    add_config_listener,
    get_config,
    get_deck_override,
    save_config,
)
from .consts import (
    DEFAULT_ALERT_NAME,
    MODULE_ADDON,
    PATH_SOUNDS,
    PATH_USERFILES,
    PYCMD_IDENTIFIER,
)
from .settings_schema import (
    ACTION_LABELS,
    EASE_FOR_ACTION,
    apply_adaptive,
    effective_settings,
    has_any_timer,
)
from .stats import queries, store
from .timer import TimerGroup

_THRESHOLD_CACHE_SECONDS = 60.0


@dataclass
class _Event:
    deadline: float
    label: str


@dataclass
class _Session:
    timers: TimerGroup = field(default_factory=TimerGroup)
    events: list[_Event] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)
    phase: str = "idle"
    phase_start: float = 0.0
    front_ms: int = 0
    deck_id: int = 0
    card_deck_id: int = 0
    card_type: int = 0
    auto_answering: bool = False
    auto_advance_previous: bool | None = None

    def reset(self) -> None:
        self.timers.clear()
        self.events.clear()
        self.settings = {}
        self.phase = "idle"
        self.auto_answering = False
        self.front_ms = 0
        self.auto_advance_previous = None


_session = _Session()

# (deck, window, slow percentile, fast percentile) -> (timestamp, slow, fast)
_threshold_cache: dict[tuple[int, int, float, float], tuple[float, float | None, float | None]] = {}


def _invalidate_caches() -> None:
    _threshold_cache.clear()


def _suppress_auto_advance() -> None:
    reviewer = mw.reviewer
    if reviewer is None:
        return
    if _session.auto_advance_previous is None:
        _session.auto_advance_previous = bool(getattr(reviewer, "auto_advance_enabled", False))
    reviewer.auto_advance_enabled = False


def _restore_auto_advance() -> None:
    reviewer = mw.reviewer
    if reviewer is not None and _session.auto_advance_previous is not None:
        reviewer.auto_advance_enabled = _session.auto_advance_previous
    _session.auto_advance_previous = None


def _alert_path() -> str:
    name = str(get_config().get("alertSound", "default") or "default")
    if name != "default":
        candidate = os.path.join(PATH_USERFILES, name)
        if os.path.isfile(candidate):
            return candidate
    return os.path.join(PATH_SOUNDS, DEFAULT_ALERT_NAME)


def _eval(js: str) -> None:
    reviewer = mw.reviewer
    if reviewer is None:
        return
    web = getattr(reviewer, "web", None)
    if web is None:
        return
    try:
        web.eval(js)
    except Exception:
        # The reviewer webview may be tearing down while a timer fires.
        pass


def _push_overlay_config() -> None:
    ui = get_config().get("ui", {})
    position = json.dumps(ui.get("overlayPosition", "top-right"))
    font_size = int(ui.get("overlayFontSize", 12))
    x_percent = float(ui.get("overlayXPercent", 70.0))
    y_percent = float(ui.get("overlayYPercent", 8.0))
    _eval(
        "if (window.speedupConfigure) "
        f"speedupConfigure({position}, {font_size}, {x_percent}, {y_percent});"
    )


def _save_overlay_position(x_percent: float, y_percent: float) -> None:
    """Persist a dragged overlay position as viewport percentages."""
    x_percent = min(100.0, max(0.0, float(x_percent)))
    y_percent = min(100.0, max(0.0, float(y_percent)))
    config = deepcopy(get_config())
    ui = dict(config.get("ui", {}))
    ui["overlayPosition"] = "custom"
    ui["overlayXPercent"] = round(x_percent, 2)
    ui["overlayYPercent"] = round(y_percent, 2)
    config["ui"] = ui
    save_config(config)


def _push_next_countdown() -> None:
    if not _session.events:
        _eval('speedupSetIdle("");')
        _eval("speedupSetMoreTimeVisible(false);")
        return
    if not get_config().get("ui", {}).get("showCountdown", True):
        _eval('speedupSetIdle("");')
        return
    event = min(_session.events, key=lambda item: item.deadline)
    remaining = max(0.0, event.deadline - time.monotonic())
    _eval(f"speedupSetCountdown({json.dumps(event.label)}, {remaining:.3f});")


def _schedule(seconds: float, label: str, callback: Callable[[], None]) -> None:
    event = _Event(deadline=time.monotonic() + seconds, label=label)
    _session.events.append(event)

    def wrapped() -> None:
        if event in _session.events:
            _session.events.remove(event)
        _push_next_countdown()
        callback()

    _session.timers.schedule(seconds * 1000.0, wrapped)


def _cancel_timers(idle_text: str = "") -> None:
    _session.timers.clear()
    _session.events.clear()
    _eval(f"speedupSetIdle({json.dumps(idle_text)});speedupSetMoreTimeVisible(false);")


def _deck_thresholds(
    deck_id: int, days: int, slow_percentile: float, fast_percentile: float
) -> tuple[float | None, float | None]:
    """Slow/fast thresholds from the local analytics database.

    The same source is used for per-card badges and per-card averages so the
    numbers stay consistent even when Anki's revlog has no front/back split.
    """
    key = (int(deck_id), int(days), float(slow_percentile), float(fast_percentile))
    now = time.monotonic()
    cached = _threshold_cache.get(key)
    if cached is not None and now - cached[0] < _THRESHOLD_CACHE_SECONDS:
        return cached[1], cached[2]

    cards = store.card_stats(int(deck_id), int(days))
    values = [float(card["total"]) for card in cards if card["total"] > 0]
    slow = queries.percentile(values, slow_percentile / 100.0) if values else None
    fast = queries.percentile(values, fast_percentile / 100.0) if values else None
    _threshold_cache[key] = (now, slow, fast)
    return slow, fast


def _push_stats(deck_id: int, card: Card | None = None) -> None:
    config = get_config()
    ui = config.get("ui", {})
    analytics = config.get("analytics", {})
    period = ui.get("totalPeriod", "today")
    stats: dict[str, Any] = {
        "average": None,
        "deckTotal": None,
        "overallTotal": None,
        "badge": None,
    }

    try:
        if ui.get("showAverage"):
            average = queries.deck_average_ms(deck_id, period=ui.get("averagePeriod", "today"))
            if average is not None:
                stats["average"] = average / 1000.0
        if ui.get("showDeckTotal"):
            stats["deckTotal"] = queries.deck_total_ms(deck_id, period=period) / 1000.0
        if ui.get("showOverallTotal"):
            stats["overallTotal"] = queries.overall_total_ms(period=period) / 1000.0
        if analytics.get("enabled") and analytics.get("markSlowFast") and card is not None:
            averages = store.card_averages(int(card.id), 30)
            if averages:
                total = averages[0] + averages[1]
                slow, fast = _deck_thresholds(
                    deck_id,
                    30,
                    float(analytics.get("slowPercentile", 75)),
                    float(analytics.get("fastPercentile", 25)),
                )
                if slow is not None and total >= slow:
                    stats["badge"] = "slow"
                elif fast is not None and total <= fast:
                    stats["badge"] = "fast"
    except Exception:
        # Stats are decorative; never let a query failure break review.
        pass

    _eval(f"speedupSetStats({json.dumps(stats)});")


def _play_alert() -> None:
    try:
        av_player.clear_queue_and_maybe_interrupt()
        av_player.play_file(_alert_path())
    except Exception:
        pass
    tooltip("Speedup alert", period=1000)


def _reveal() -> None:
    reviewer = mw.reviewer
    if reviewer is not None and reviewer.state == "question":
        reviewer._showAnswer()


def _do_action(action: str) -> None:
    reviewer = mw.reviewer
    if reviewer is None or reviewer.card is None:
        return
    if action == "bury":
        _session.timers.clear()
        _session.events.clear()
        _restore_auto_advance()
        reviewer.bury_current_card()
        return
    ease = EASE_FOR_ACTION.get(action)
    if ease is None:
        return
    if reviewer.state == "question":
        _session.auto_answering = True
        reviewer._showAnswer()
    if reviewer.state == "answer":
        reviewer._answerCard(ease)


def _reviewed_deck_id(fallback: int) -> int:
    """The deck the user is currently studying, which may be a parent deck.

    A card may live in a subdeck (e.g. "JP Vocab::Mining") while the user
    reviews its parent ("JP Vocab"); stats should reflect the reviewed deck.
    """
    if mw.col is None:
        return fallback
    try:
        deck = mw.col.decks.current()
    except Exception:
        return fallback
    if deck and deck.get("id"):
        return int(deck["id"])
    return fallback


def _settings_for_card(card: Card, deck_id: int) -> dict[str, Any]:
    """Resolve timings from the preset of the deck currently being reviewed.

    Using the reviewed deck (rather than the card's own subdeck) means a
    parent deck's settings also govern reviews/custom study sessions that
    pull in cards from its subdecks.
    """
    config = get_config()
    override = get_deck_override(deck_id)
    settings = effective_settings(config, override, card.type)

    adaptive = config.get("adaptive", {})
    if settings.get("enabled") and adaptive.get("enabled"):
        averages = store.deck_averages(deck_id, adaptive.get("windowDays", 30))
        if averages:
            adapted = apply_adaptive(
                settings,
                averages[0] / 1000.0,
                averages[1] / 1000.0,
                factor=float(adaptive.get("factor", 0.97)),
                floor=float(adaptive.get("floor", 1.0)),
            )
            adapted["enabled"] = settings.get("enabled", True)
            adapted["cardClass"] = settings.get("cardClass")
            settings = adapted
    return settings


def _start_question(card: Card) -> None:
    _restore_auto_advance()
    _session.reset()
    config = get_config()

    _session.card_deck_id = int(card.current_deck_id())
    _session.deck_id = _reviewed_deck_id(_session.card_deck_id)
    settings = _settings_for_card(card, _session.deck_id)

    _session.settings = settings
    _session.card_type = int(card.type)
    _session.phase = "question"
    _session.phase_start = time.monotonic()

    _eval("if (window.speedupBuild) speedupBuild();")
    _push_overlay_config()
    _push_stats(_session.deck_id, card)

    if not has_any_timer(settings):
        _eval("speedupSetMoreTimeVisible(false);")
        _eval('speedupSetIdle("");')
        return

    if config.get("suppressBuiltInAutoAdvance", True):
        _suppress_auto_advance()

    show_more = bool(config.get("moreTime", {}).get("showButton", False))
    _eval(f"speedupSetMoreTimeVisible({'true' if show_more else 'false'});")

    question = settings.get("question", {})
    if question.get("alertAfter", 0) > 0:
        _schedule(float(question["alertAfter"]), "Alert", _play_alert)
    if question.get("revealAfter", 0) > 0:
        _schedule(float(question["revealAfter"]), "Reveal", _reveal)
    auto_action = question.get("autoAction", {})
    if auto_action.get("after", 0) > 0:
        action = str(auto_action.get("action", "again"))
        _schedule(
            float(auto_action["after"]),
            ACTION_LABELS.get(action, action),
            partial(_do_action, action),
        )

    _push_next_countdown()


def _start_answer(card: Card) -> None:
    if _session.phase == "question":
        _session.front_ms = int((time.monotonic() - _session.phase_start) * 1000)

    _session.timers.clear()
    _session.events.clear()

    if _session.auto_answering:
        _session.auto_answering = False
        return

    _session.phase = "answer"
    _session.phase_start = time.monotonic()

    settings = _session.settings
    if not has_any_timer(settings):
        _push_next_countdown()
        return

    answer = settings.get("answer", {})
    if answer.get("alertAfter", 0) > 0:
        _schedule(float(answer["alertAfter"]), "Alert", _play_alert)
    auto_action = answer.get("autoAction", {})
    if auto_action.get("after", 0) > 0:
        action = str(auto_action.get("action", "good"))
        _schedule(
            float(auto_action["after"]),
            ACTION_LABELS.get(action, action),
            partial(_do_action, action),
        )

    _push_next_countdown()


def _on_show_question(card: Card) -> None:
    if card is not None:
        _start_question(card)


def _on_show_answer(card: Card) -> None:
    if card is not None:
        _start_answer(card)


def _on_answer_card(reviewer: Reviewer, card: Card, ease: int) -> None:
    back_ms = 0
    if _session.phase == "answer":
        back_ms = int((time.monotonic() - _session.phase_start) * 1000)

    analytics_enabled = bool(get_config().get("analytics", {}).get("enabled"))
    if analytics_enabled and card is not None:
        try:
            # Store the deck being reviewed, not the card's subdeck, so the
            # per-deck statistics and adaptive timers agree with the overlay.
            store.record(
                cid=int(card.id),
                did=_session.deck_id or _session.card_deck_id,
                front_ms=_session.front_ms,
                back_ms=back_ms,
                ease=int(ease),
                card_type=_session.card_type,
            )
        except Exception:
            pass

    _restore_auto_advance()
    _session.timers.clear()
    _session.events.clear()
    _session.phase = "idle"
    _eval('speedupSetIdle("");')


def _on_more_time() -> None:
    _cancel_timers("Stopped.")
    tooltip("Timer stopped.")


def _on_typeans() -> None:
    if get_config().get("stopTimersWhenTyping", True):
        _cancel_timers("Stopped.")


def _on_js_message(handled: tuple[bool, Any], message: str, context: Any) -> tuple[bool, Any]:
    if not isinstance(message, str) or not message.startswith(PYCMD_IDENTIFIER + ":"):
        return handled
    action = message.split(":", 1)[1]
    if action.startswith("overlayMoved:"):
        try:
            payload = json.loads(action.split(":", 1)[1])
            _save_overlay_position(float(payload["x"]), float(payload["y"]))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass
    elif action == "moreTime":
        _on_more_time()
    elif action == "typeans":
        _on_typeans()
    return (True, None)


def _on_webview_will_set_content(web_content: Any, context: Any) -> None:
    config = get_config()
    hotkey = config.get("moreTime", {}).get("hotkey", "p")
    ui = config.get("ui", {})
    position = ui.get("overlayPosition", "top-right")
    font_size = int(ui.get("overlayFontSize", 12))
    x_percent = float(ui.get("overlayXPercent", 70.0))
    y_percent = float(ui.get("overlayYPercent", 8.0))
    if isinstance(context, Reviewer):
        web_content.head += (
            f"<script>window.speedupHotkey = {json.dumps(hotkey)};"
            f"window.speedupOverlayPosition = {json.dumps(position)};"
            f"window.speedupOverlayFontSize = {font_size};"
            f"window.speedupOverlayXPercent = {x_percent};"
            f"window.speedupOverlayYPercent = {y_percent};"
            "window.speedupSetIdle = window.speedupSetIdle || function(){};"
            "window.speedupSetStats = window.speedupSetStats || function(){};"
            "window.speedupSetCountdown = window.speedupSetCountdown || function(){};"
            "window.speedupSetMoreTimeVisible = window.speedupSetMoreTimeVisible || function(){};"
            "window.speedupConfigure = window.speedupConfigure || function(){};"
            "</script>"
        )
        web_content.js.append(f"/_addons/{MODULE_ADDON}/web/reviewer.js")
        web_content.js.append(f"/_addons/{MODULE_ADDON}/web/reviewer_card.js")


def _on_state_shortcuts_will_change(state: str, shortcuts: list[Any]) -> None:
    if state != "review" or not get_config().get("enabled", True):
        return
    hotkey = get_config().get("moreTime", {}).get("hotkey", "p")
    if hotkey:
        shortcuts.append((hotkey, _on_more_time))


def _on_reviewer_did_init(reviewer: Reviewer) -> None:
    _restore_auto_advance()
    _session.reset()
    _invalidate_caches()


def _on_reviewer_will_end() -> None:
    _restore_auto_advance()
    _cancel_timers("")
    _invalidate_caches()


def _on_dialog_manager_did_open_dialog(*args: Any, **kwargs: Any) -> None:
    if _session.events:
        _cancel_timers("Paused.")


def _on_config_updated() -> None:
    _invalidate_caches()
    if get_config().get("suppressBuiltInAutoAdvance", True) and _session.events:
        _suppress_auto_advance()
    elif _session.auto_advance_previous is not None:
        _restore_auto_advance()
    _push_overlay_config()
    reviewer = mw.reviewer
    if reviewer is not None and reviewer.card is not None:
        _push_stats(_session.deck_id, reviewer.card)
        _push_next_countdown()


def initialize_reviewer() -> None:
    mw.addonManager.setWebExports(MODULE_ADDON, r"web.*")
    gui_hooks.reviewer_did_init.append(_on_reviewer_did_init)
    gui_hooks.reviewer_did_show_question.append(_on_show_question)
    gui_hooks.reviewer_did_show_answer.append(_on_show_answer)
    gui_hooks.reviewer_did_answer_card.append(_on_answer_card)
    gui_hooks.reviewer_will_end.append(_on_reviewer_will_end)
    gui_hooks.state_shortcuts_will_change.append(_on_state_shortcuts_will_change)
    gui_hooks.webview_will_set_content.append(_on_webview_will_set_content)
    gui_hooks.webview_did_receive_js_message.append(_on_js_message)
    gui_hooks.dialog_manager_did_open_dialog.append(_on_dialog_manager_did_open_dialog)
    add_config_listener(_on_config_updated)
