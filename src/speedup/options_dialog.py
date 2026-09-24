# Speedup - an Anki add-on derived from Speed Focus Mode
# Copyright (C) 2026 Speedup contributors
# Based on Speed Focus Mode, Copyright (C) 2017-2022 Aristotelis P. (Glutanimate)
# License: GNU AGPL v3 or later (see LICENSE)

"""Global settings dialog for Speedup."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from aqt import mw
from aqt.qt import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QKeySequence,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    qconnect,
)
from aqt.utils import disable_help_button, restoreGeom, saveGeom

from .config_manager import get_config, save_config
from .settings_schema import (
    ACTION_LABELS,
    ACTIONS,
    CARD_CLASSES,
    default_global_settings,
)

TITLE = "SpeedupOptions"

CLASS_LABELS = {
    "new": "New",
    "learning": "Learning",
    "review": "Review",
    "relearning": "Relearning",
}


def _seconds_spin() -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(0.0, 3600.0)
    spin.setDecimals(1)
    spin.setSingleStep(0.1)
    spin.setSuffix(" s")
    return spin


def _action_combo() -> QComboBox:
    combo = QComboBox()
    for action in ACTIONS:
        combo.addItem(ACTION_LABELS[action], action)
    return combo


class _PhaseGroup(QGroupBox):
    def __init__(self, title: str, *, show_reveal: bool) -> None:
        super().__init__(title)
        self.show_reveal = show_reveal

        self.alert_after = _seconds_spin()
        self.reveal_after = _seconds_spin()
        self.action_after = _seconds_spin()
        self.action = _action_combo()

        layout = QFormLayout(self)
        layout.addRow("Play alert after", self.alert_after)
        if show_reveal:
            layout.addRow("Show answer after", self.reveal_after)
        layout.addRow("Automatically", self.action)
        layout.addRow("after", self.action_after)

    def load(self, data: dict[str, Any]) -> None:
        auto_action = data.get("autoAction", {})
        self.alert_after.setValue(float(data.get("alertAfter", 0.0) or 0.0))
        self.reveal_after.setValue(float(data.get("revealAfter", 0.0) or 0.0))
        self.action_after.setValue(float(auto_action.get("after", 0.0) or 0.0))
        index = self.action.findData(auto_action.get("action", "again"))
        self.action.setCurrentIndex(max(0, index))

    def dump(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "alertAfter": round(self.alert_after.value(), 1),
            "autoAction": {
                "after": round(self.action_after.value(), 1),
                "action": self.action.currentData(),
            },
        }
        if self.show_reveal:
            data["revealAfter"] = round(self.reveal_after.value(), 1)
        return data


class _ClassTab(QWidget):
    def __init__(self, card_class: str) -> None:
        super().__init__()
        self.card_class = card_class
        self.question = _PhaseGroup("Question", show_reveal=True)
        self.answer = _PhaseGroup("Answer", show_reveal=False)
        layout = QVBoxLayout(self)
        layout.addWidget(self.question)
        layout.addWidget(self.answer)
        layout.addStretch()

    def load(self, data: dict[str, Any]) -> None:
        self.question.load(data.get("question", {}))
        self.answer.load(data.get("answer", {}))

    def dump(self) -> dict[str, Any]:
        return {
            "question": self.question.dump(),
            "answer": self.answer.dump(),
        }


class SpeedupOptionsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent or mw)
        self.setWindowTitle("Speedup Options")
        disable_help_button(self)
        restoreGeom(self, TITLE, default_size=(520, 640))

        config = deepcopy(get_config())
        defaults = default_global_settings()

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_general(config, defaults), "General")

        self.class_tabs: dict[str, _ClassTab] = {}
        for card_class in CARD_CLASSES:
            tab = _ClassTab(card_class)
            tab.load(config["defaults"].get(card_class, {}))
            self.class_tabs[card_class] = tab
            self.tabs.addTab(tab, CLASS_LABELS[card_class])

        self.tabs.addTab(self._build_display(config, defaults), "Display")
        self.tabs.addTab(self._build_analytics(config, defaults), "Analytics")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        qconnect(buttons.accepted, self.accept)
        qconnect(buttons.rejected, self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addWidget(buttons)

    def _build_general(self, config: dict[str, Any], defaults: dict[str, Any]) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.enabled = QCheckBox("Enable Speedup timers")
        self.enabled.setChecked(bool(config.get("enabled", True)))

        self.suppress_builtin = QCheckBox(
            "Suppress Anki's built-in Auto Advance while Speedup timers are active"
        )
        self.suppress_builtin.setChecked(
            bool(config.get("suppressBuiltInAutoAdvance", True))
        )

        self.stop_typing = QCheckBox("Stop timers when typing the answer")
        self.stop_typing.setChecked(bool(config.get("stopTimersWhenTyping", True)))

        self.show_more_time = QCheckBox('Show the "More time" button and countdown')
        self.show_more_time.setChecked(
            bool(config.get("moreTime", {}).get("showButton", False))
        )

        self.hotkey = QKeySequenceEdit(
            QKeySequence(config.get("moreTime", {}).get("hotkey", "p") or "p")
        )

        self.alert_sound = QLineEdit(config.get("alertSound", "default") or "default")
        self.alert_sound.setToolTip(
            'Enter "default" to use the bundled sound, or the name of a file in the '
            "add-on's user_files folder."
        )

        self.collapse_new_learning = QCheckBox("Use one set of settings for New + Learning")
        self.collapse_new_learning.setChecked(
            bool(config.get("grouping", {}).get("collapseNewLearning", False))
        )
        self.collapse_review_relearning = QCheckBox(
            "Use one set of settings for Review + Relearning"
        )
        self.collapse_review_relearning.setChecked(
            bool(config.get("grouping", {}).get("collapseReviewRelearning", False))
        )

        form = QFormLayout()
        form.addRow("More time hotkey", self.hotkey)
        form.addRow("Alert sound", self.alert_sound)

        layout.addWidget(self.enabled)
        layout.addWidget(self.suppress_builtin)
        layout.addWidget(self.stop_typing)
        layout.addWidget(self.show_more_time)
        layout.addLayout(form)
        layout.addWidget(QLabel("<b>Card classes</b>"))
        layout.addWidget(self.collapse_new_learning)
        layout.addWidget(self.collapse_review_relearning)
        layout.addStretch()
        return widget

    def _build_display(self, config: dict[str, Any], defaults: dict[str, Any]) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        ui = config.get("ui", {})

        self.show_countdown = QCheckBox("Show countdown to the next timer")
        self.show_countdown.setChecked(bool(ui.get("showCountdown", True)))

        self.show_average = QCheckBox("Show average time per card")
        self.show_average.setChecked(bool(ui.get("showAverage", False)))

        self.show_deck_total = QCheckBox("Show total time on this deck")
        self.show_deck_total.setChecked(bool(ui.get("showDeckTotal", False)))

        self.show_overall_total = QCheckBox("Show total time overall")
        self.show_overall_total.setChecked(bool(ui.get("showOverallTotal", False)))

        self.total_period = QComboBox()
        self.total_period.addItem("Today", "today")
        self.total_period.addItem("All time", "all")
        index = self.total_period.findData(ui.get("totalPeriod", "today"))
        self.total_period.setCurrentIndex(max(0, index))

        form = QFormLayout()
        form.addRow("Total time period", self.total_period)

        layout.addWidget(self.show_countdown)
        layout.addWidget(self.show_average)
        layout.addWidget(self.show_deck_total)
        layout.addWidget(self.show_overall_total)
        layout.addLayout(form)
        layout.addStretch()
        return widget

    def _build_analytics(
        self, config: dict[str, Any], defaults: dict[str, Any]
    ) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        analytics = config.get("analytics", {})
        adaptive = config.get("adaptive", {})

        self.analytics_enabled = QCheckBox(
            "Record per-card front/back times locally (opt-in)"
        )
        self.analytics_enabled.setChecked(bool(analytics.get("enabled", False)))

        self.mark_slow_fast = QCheckBox("Mark slow/fast cards in the reviewer")
        self.mark_slow_fast.setChecked(bool(analytics.get("markSlowFast", False)))

        self.slow_percentile = QSpinBox()
        self.slow_percentile.setRange(50, 99)
        self.slow_percentile.setValue(int(analytics.get("slowPercentile", 75)))

        self.fast_percentile = QSpinBox()
        self.fast_percentile.setRange(1, 50)
        self.fast_percentile.setValue(int(analytics.get("fastPercentile", 25)))

        self.adaptive_enabled = QCheckBox(
            "Gradually speed up timers based on your recent averages"
        )
        self.adaptive_enabled.setChecked(bool(adaptive.get("enabled", False)))

        self.adaptive_factor = QDoubleSpinBox()
        self.adaptive_factor.setRange(0.5, 1.0)
        self.adaptive_factor.setDecimals(2)
        self.adaptive_factor.setSingleStep(0.01)
        self.adaptive_factor.setValue(float(adaptive.get("factor", 0.97)))

        self.adaptive_window = QSpinBox()
        self.adaptive_window.setRange(1, 365)
        self.adaptive_window.setValue(int(adaptive.get("windowDays", 30)))

        self.adaptive_floor = QDoubleSpinBox()
        self.adaptive_floor.setRange(0.0, 60.0)
        self.adaptive_floor.setDecimals(1)
        self.adaptive_floor.setSingleStep(0.1)
        self.adaptive_floor.setSuffix(" s")
        self.adaptive_floor.setValue(float(adaptive.get("floor", 1.0)))

        form = QFormLayout()
        form.addRow("Slow threshold (percentile)", self.slow_percentile)
        form.addRow("Fast threshold (percentile)", self.fast_percentile)
        form.addRow("Speed-up factor", self.adaptive_factor)
        form.addRow("Rolling window (days)", self.adaptive_window)
        form.addRow("Minimum time", self.adaptive_floor)

        layout.addWidget(self.analytics_enabled)
        layout.addWidget(self.mark_slow_fast)
        layout.addLayout(form)
        layout.addWidget(QLabel("<b>Adaptive speed-up</b>"))
        layout.addWidget(self.adaptive_enabled)
        layout.addStretch()
        return widget

    def result_config(self) -> dict[str, Any]:
        config = deepcopy(get_config())

        config["enabled"] = self.enabled.isChecked()
        config["suppressBuiltInAutoAdvance"] = self.suppress_builtin.isChecked()
        config["stopTimersWhenTyping"] = self.stop_typing.isChecked()
        config["alertSound"] = self.alert_sound.text().strip() or "default"
        config["moreTime"] = {
            "showButton": self.show_more_time.isChecked(),
            "hotkey": self.hotkey.keySequence().toString() or "p",
        }
        config["grouping"] = {
            "collapseNewLearning": self.collapse_new_learning.isChecked(),
            "collapseReviewRelearning": self.collapse_review_relearning.isChecked(),
        }
        config["defaults"] = {
            card_class: self.class_tabs[card_class].dump()
            for card_class in CARD_CLASSES
        }
        config["ui"] = {
            "showCountdown": self.show_countdown.isChecked(),
            "showAverage": self.show_average.isChecked(),
            "showDeckTotal": self.show_deck_total.isChecked(),
            "showOverallTotal": self.show_overall_total.isChecked(),
            "totalPeriod": self.total_period.currentData(),
        }
        config["analytics"] = {
            "enabled": self.analytics_enabled.isChecked(),
            "markSlowFast": self.mark_slow_fast.isChecked(),
            "slowPercentile": self.slow_percentile.value(),
            "fastPercentile": self.fast_percentile.value(),
        }
        config["adaptive"] = {
            "enabled": self.adaptive_enabled.isChecked(),
            "factor": round(self.adaptive_factor.value(), 2),
            "windowDays": self.adaptive_window.value(),
            "floor": round(self.adaptive_floor.value(), 1),
        }
        return config

    def accept(self) -> None:
        save_config(self.result_config())
        saveGeom(self, TITLE)
        super().accept()

    def reject(self) -> None:
        saveGeom(self, TITLE)
        super().reject()


def show_options_dialog() -> None:
    dialog = SpeedupOptionsDialog()
    dialog.exec()
