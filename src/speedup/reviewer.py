# Speedup - an Anki add-on derived from Speed Focus Mode
# Copyright (C) 2026 Speedup contributors
# Based on Speed Focus Mode, Copyright (C) 2017-2022 Aristotelis P. (Glutanimate)
# License: GNU AGPL v3 or later (see LICENSE)

"""Reviewer timing engine and bottom-bar UI."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from anki.cards import Card
from aqt import gui_hooks, mw
from aqt.reviewer import Reviewer
from aqt.sound import av_player
from aqt.utils import tooltip

from .config_manager import get_config, get_deck_override
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
    card_type: int = 0
    auto_answering: bool = False

    def reset(self) -> None:
        self.timers.clear()
        self.events.clear()
        self.settings = {}
        self.phase = "idle"
        self.auto_answering = False
        self.front_ms = 0


_session = _Session()

_percentile_cache: dict[int, tuple[float | None, float | None]] = {}


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
    web.eval(js)


def _push_next_countdown() -> None:
    if not get_config().get("ui", {}).get("showCountdown", True):
        return
    if not _session.events:
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
    _eval(f"speedupSetIdle({json.dumps(idle_text)});")


def _deck_thresholds(
    deck_id: int, days: int, slow_percentile: float, fast_percentile: float
) -> tuple[float | None, float | None]:
    cached = _percentile_cache.get(deck_id)
    if cached is not None:
        return cached
    averages = queries.card_average_map(deck_id, days=days)
    values = [value for value in averages.values() if value]
    slow = queries.percentile(values, slow_percentile / 100.0) if values else None
    fast = queries.percentile(values, fast_percentile / 100.0) if values else None
    result = (slow, fast)
    _percentile_cache[deck_id] = result
    return result


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
    if ui.get("showAverage"):
        average = queries.deck_average_ms(deck_id, period="all")
        if average:
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


def _settings_for_card(card: Card) -> dict[str, Any]:
    config = get_config()
    deck_id = int(card.current_deck_id())
    override = get_deck_override(deck_id)
    settings = effective_settings(config, override, card.type)

    adaptive = config.get("adaptive", {})
    if settings.get("enabled") and adaptive.get("enabled"):
        averages = store.deck_averages(deck_id, adaptive.get("windowDays", 30))
        if averages:
            settings = apply_adaptive(
                settings,
                averages[0] / 1000.0,
                averages[1] / 1000.0,
                factor=float(adaptive.get("factor", 0.97)),
                floor=float(adaptive.get("floor", 1.0)),
            )
    return settings


def _start_question(card: Card) -> None:
    _session.reset()
    config = get_config()
    settings = _settings_for_card(card)

    _session.settings = settings
    _session.deck_id = int(card.current_deck_id())
    _session.card_type = int(card.type)
    _session.phase = "question"
    _session.phase_start = time.monotonic()

    _eval("if (window.speedupBuild) speedupBuild();")
    ui = config.get("ui", {})
    position = ui.get("overlayPosition", "top-right")
    font_size = int(ui.get("overlayFontSize", 12))
    _eval(
        "if (window.speedupConfigure) "
        f"speedupConfigure({json.dumps(position)}, {font_size});"
    )
    _push_stats(_session.deck_id, card)

    if not has_any_timer(settings):
        _eval("speedupSetMoreTimeVisible(false);")
        _eval('speedupSetIdle("");')
        return

    if config.get("suppressBuiltInAutoAdvance", True) and mw.reviewer is not None:
        mw.reviewer.auto_advance_enabled = False

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
            lambda chosen=action: _do_action(chosen),
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
            lambda chosen=action: _do_action(chosen),
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

    if get_config().get("analytics", {}).get("enabled") and card is not None:
        try:
            store.record(
                cid=int(card.id),
                did=_session.deck_id,
                front_ms=_session.front_ms,
                back_ms=back_ms,
                ease=int(ease),
                card_type=_session.card_type,
            )
        except Exception:
            pass

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


def _on_js_message(
    handled: tuple[bool, Any], message: str, context: Any
) -> tuple[bool, Any]:
    if not isinstance(message, str) or not message.startswith(PYCMD_IDENTIFIER + ":"):
        return handled
    action = message.split(":", 1)[1]
    if action == "moreTime":
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
    if isinstance(context, Reviewer):
        web_content.body += (
            f"<script>window.speedupHotkey = {json.dumps(hotkey)};"
            f"window.speedupOverlayPosition = {json.dumps(position)};"
            f"window.speedupOverlayFontSize = {font_size};"
            "window.speedupSetIdle = window.speedupSetIdle || function(){};"
            "window.speedupSetStats = window.speedupSetStats || function(){};"
            "window.speedupSetCountdown = window.speedupSetCountdown || function(){};"
            "window.speedupSetMoreTimeVisible = window.speedupSetMoreTimeVisible || function(){};"
            "window.speedupConfigure = window.speedupConfigure || function(){};"
            "</script>"
            f'<script src="/_addons/{MODULE_ADDON}/web/reviewer.js"></script>'
            f'<script src="/_addons/{MODULE_ADDON}/web/reviewer_card.js"></script>'
        )


def _on_state_shortcuts_will_change(state: str, shortcuts: list[Any]) -> None:
    if state != "review":
        return
    hotkey = get_config().get("moreTime", {}).get("hotkey", "p")
    if hotkey:
        shortcuts.append((hotkey, _on_more_time))


def _on_reviewer_did_init(reviewer: Reviewer) -> None:
    _session.reset()


def _on_reviewer_will_end() -> None:
    _cancel_timers("")


def _on_dialog_manager_did_open_dialog(*args: Any, **kwargs: Any) -> None:
    if _session.events:
        _cancel_timers("Paused.")


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
