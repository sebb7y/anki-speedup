# Speedup - an Anki add-on derived from Speed Focus Mode
# Copyright (C) 2026 Speedup contributors
# Based on Speed Focus Mode, Copyright (C) 2017-2022 Aristotelis P. (Glutanimate)
# License: GNU AGPL v3 or later (see LICENSE)

"""Global settings dialog for Speedup."""

from __future__ import annotations

import os
from copy import deepcopy
from typing import Any

from aqt import mw
from aqt.qt import (
    QCheckBox,
    QComboBox,
    QDesktopServices,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QKeySequence,
    QKeySequenceEdit,
    QLabel,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QUrl,
    QVBoxLayout,
    QWidget,
    qconnect,
)
from aqt.sound import av_player
from aqt.utils import disable_help_button, restoreGeom, saveGeom, tooltip

from .config_manager import get_config, save_config
from .consts import DEFAULT_ALERT_NAME, PATH_SOUNDS, PATH_USERFILES
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

SOUND_EXTENSIONS = (".mp3", ".wav", ".ogg", ".m4a", ".flac")


def _sound_choices() -> list[str]:
    choices = ["default"]
    try:
        names = sorted(os.listdir(PATH_USERFILES))
    except OSError:
        names = []
    for name in names:
        if name.lower().endswith(SOUND_EXTENSIONS):
            choices.append(name)
    return choices


def _resolve_sound(name: str) -> str:
    name = (name or "default").strip() or "default"
    if name != "default":
        candidate = os.path.join(PATH_USERFILES, name)
        if os.path.isfile(candidate):
            return candidate
    return os.path.join(PATH_SOUNDS, DEFAULT_ALERT_NAME)


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
        self.alert_after.setToolTip("Play the alert sound after this many seconds.")
        self.reveal_after = _seconds_spin()
        self.reveal_after.setToolTip("Reveal the answer after this many seconds.")
        self.action_after = _seconds_spin()
        self.action_after.setToolTip("Perform the action after this many seconds.")
        self.action = _action_combo()
        self.action.setToolTip("What to do when the timer expires.")

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

        note = QLabel(
            "Times are in seconds and may be fractional (e.g. <code>2.7</code>). "
            "A value of <code>0</code> disables that timer."
        )
        note.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(note)
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
        restoreGeom(self, TITLE, default_size=(560, 680))

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_general(), "General")

        self.class_tabs: dict[str, _ClassTab] = {}
        for card_class in CARD_CLASSES:
            tab = _ClassTab(card_class)
            self.class_tabs[card_class] = tab
            self.tabs.addTab(tab, CLASS_LABELS[card_class])

        self.tabs.addTab(self._build_display(), "Display")
        self.tabs.addTab(self._build_analytics(), "Analytics")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.RestoreDefaults
        )
        qconnect(buttons.accepted, self.accept)
        qconnect(buttons.rejected, self.reject)
        restore_button = buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults)
        if restore_button is not None:
            qconnect(restore_button.clicked, self._restore_defaults)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addWidget(buttons)

        self._load_config(get_config())

    def _build_general(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.enabled = QCheckBox("Enable Speedup timers")
        self.enabled.setToolTip("Master switch for all timers and the More time shortcut.")

        self.suppress_builtin = QCheckBox(
            "Suppress Anki's built-in Auto Advance while Speedup timers are active"
        )
        self.suppress_builtin.setToolTip(
            "Prevents two automatic systems from advancing the same card."
        )

        self.stop_typing = QCheckBox("Stop timers when typing the answer")
        self.stop_typing.setToolTip(
            "Useful for type-in-answer cards: the clock stops as soon as you start typing."
        )

        self.show_more_time = QCheckBox('Show the "More time" button')
        self.show_more_time.setToolTip(
            "The countdown is always clickable, even when this button is hidden."
        )

        self.hotkey = QKeySequenceEdit(QKeySequence("p"))
        self.hotkey.setMaximumSequenceLength(1)
        self.hotkey.setToolTip(
            "Shortcut that stops the current timers. Avoid keys Anki already uses."
        )

        self.alert_sound = QComboBox()
        self.alert_sound.setEditable(True)
        self.alert_sound.addItems(_sound_choices())
        self.alert_sound.setToolTip(
            'Choose "default" for the bundled sound, or a file placed in the user_files folder.'
        )

        self.test_sound = QPushButton("Test")
        qconnect(self.test_sound.clicked, self._test_alert_sound)
        self.open_sounds = QPushButton("Open folder")
        qconnect(self.open_sounds.clicked, self._open_user_files)

        sound_row = QHBoxLayout()
        sound_row.addWidget(self.alert_sound, 1)
        sound_row.addWidget(self.test_sound)
        sound_row.addWidget(self.open_sounds)

        self.collapse_new_learning = QCheckBox("Use one set of settings for New + Learning")
        self.collapse_review_relearning = QCheckBox(
            "Use one set of settings for Review + Relearning"
        )
        qconnect(self.collapse_new_learning.toggled, self._update_class_tabs)
        qconnect(self.collapse_review_relearning.toggled, self._update_class_tabs)

        grouping_note = QLabel(
            "Collapsed classes use the New or Review timings. The matching tab is "
            "disabled so it is clear which settings are active."
        )
        grouping_note.setWordWrap(True)

        form = QFormLayout()
        form.addRow("More time hotkey", self.hotkey)
        form.addRow("Alert sound", sound_row)

        layout.addWidget(self.enabled)
        layout.addWidget(self.suppress_builtin)
        layout.addWidget(self.stop_typing)
        layout.addWidget(self.show_more_time)
        layout.addLayout(form)
        layout.addWidget(QLabel("<b>Card classes</b>"))
        layout.addWidget(self.collapse_new_learning)
        layout.addWidget(self.collapse_review_relearning)
        layout.addWidget(grouping_note)
        layout.addStretch()
        return widget

    def _build_display(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.show_countdown = QCheckBox("Show countdown to the next timer")
        self.show_countdown.setToolTip("Click the countdown to stop the current timers.")

        self.show_average = QCheckBox("Show average time per card")
        self.show_average.setToolTip("Uses Anki's revlog for the deck currently being reviewed.")

        self.show_deck_total = QCheckBox("Show total time on this deck")
        self.show_overall_total = QCheckBox("Show total time overall")

        self.total_period = QComboBox()
        self.total_period.addItem("Today", "today")
        self.total_period.addItem("All time", "all")

        self.average_period = QComboBox()
        self.average_period.addItem("Today", "today")
        self.average_period.addItem("All time", "all")

        self.overlay_position = QComboBox()
        self.overlay_position.addItem("Top right", "top-right")
        self.overlay_position.addItem("Top left", "top-left")
        self.overlay_position.addItem("Bottom right", "bottom-right")
        self.overlay_position.addItem("Bottom left", "bottom-left")
        self.overlay_position.addItem("Custom (drag)", "custom")

        self.overlay_font_size = QSpinBox()
        self.overlay_font_size.setRange(8, 48)
        self.overlay_font_size.setSuffix(" px")

        form = QFormLayout()
        form.addRow("Total time period", self.total_period)
        form.addRow("Average time period", self.average_period)
        form.addRow("Overlay position", self.overlay_position)
        form.addRow("Overlay text size", self.overlay_font_size)

        drag_note = QLabel(
            "For a custom position, choose <b>Custom (drag)</b>, then drag the "
            "⠿ handle on the reviewer overlay. The position is remembered."
        )
        drag_note.setWordWrap(True)

        layout.addWidget(self.show_countdown)
        layout.addWidget(self.show_average)
        layout.addWidget(self.show_deck_total)
        layout.addWidget(self.show_overall_total)
        layout.addLayout(form)
        layout.addWidget(drag_note)
        layout.addStretch()
        return widget

    def _build_analytics(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        note = QLabel(
            "Analytics stores per-card front/back times in a local database "
            "(<code>user_files/speedup.db</code>). It is not synced. Open "
            "<b>Tools → Speedup → Statistics…</b> to see the results."
        )
        note.setWordWrap(True)

        self.analytics_enabled = QCheckBox("Record per-card front/back times locally (opt-in)")
        qconnect(self.analytics_enabled.toggled, self._update_analytics_controls)

        self.mark_slow_fast = QCheckBox("Mark slow/fast cards in the reviewer")

        self.slow_percentile = QSpinBox()
        self.slow_percentile.setRange(50, 99)
        self.slow_percentile.setToolTip("Cards at or above this percentile are marked slow.")

        self.fast_percentile = QSpinBox()
        self.fast_percentile.setRange(1, 50)
        self.fast_percentile.setToolTip("Cards at or below this percentile are marked fast.")

        self.adaptive_enabled = QCheckBox("Gradually speed up timers based on your recent averages")
        self.adaptive_enabled.setToolTip("Requires per-card analytics to be enabled first.")
        qconnect(self.adaptive_enabled.toggled, self._update_analytics_controls)

        self.adaptive_factor = QDoubleSpinBox()
        self.adaptive_factor.setRange(0.5, 1.0)
        self.adaptive_factor.setDecimals(2)
        self.adaptive_factor.setSingleStep(0.01)
        self.adaptive_factor.setToolTip(
            "Multiplier applied to your recent averages. Lower is faster."
        )

        self.adaptive_window = QSpinBox()
        self.adaptive_window.setRange(1, 365)
        self.adaptive_window.setSuffix(" days")

        self.adaptive_floor = QDoubleSpinBox()
        self.adaptive_floor.setRange(0.0, 60.0)
        self.adaptive_floor.setDecimals(1)
        self.adaptive_floor.setSingleStep(0.1)
        self.adaptive_floor.setSuffix(" s")

        form = QFormLayout()
        form.addRow("Slow threshold (percentile)", self.slow_percentile)
        form.addRow("Fast threshold (percentile)", self.fast_percentile)
        form.addRow("Speed-up factor", self.adaptive_factor)
        form.addRow("Rolling window", self.adaptive_window)
        form.addRow("Minimum time", self.adaptive_floor)

        layout.addWidget(note)
        layout.addWidget(self.analytics_enabled)
        layout.addWidget(self.mark_slow_fast)
        layout.addLayout(form)
        layout.addWidget(QLabel("<b>Adaptive speed-up</b>"))
        layout.addWidget(self.adaptive_enabled)
        layout.addStretch()
        return widget

    def _load_config(self, config: dict[str, Any]) -> None:
        more_time = config.get("moreTime", {})
        grouping = config.get("grouping", {})
        ui = config.get("ui", {})
        analytics = config.get("analytics", {})
        adaptive = config.get("adaptive", {})

        self.enabled.setChecked(bool(config.get("enabled", True)))
        self.suppress_builtin.setChecked(bool(config.get("suppressBuiltInAutoAdvance", True)))
        self.stop_typing.setChecked(bool(config.get("stopTimersWhenTyping", True)))
        self.show_more_time.setChecked(bool(more_time.get("showButton", False)))
        self.hotkey.setKeySequence(QKeySequence(more_time.get("hotkey", "p") or "p"))
        self.alert_sound.setCurrentText(str(config.get("alertSound", "default") or "default"))
        self.collapse_new_learning.setChecked(bool(grouping.get("collapseNewLearning", False)))
        self.collapse_review_relearning.setChecked(
            bool(grouping.get("collapseReviewRelearning", False))
        )

        defaults = config.get("defaults", {})
        for card_class, tab in self.class_tabs.items():
            tab.load(defaults.get(card_class, {}))

        self.show_countdown.setChecked(bool(ui.get("showCountdown", True)))
        self.show_average.setChecked(bool(ui.get("showAverage", False)))
        self.show_deck_total.setChecked(bool(ui.get("showDeckTotal", False)))
        self.show_overall_total.setChecked(bool(ui.get("showOverallTotal", False)))

        total_index = self.total_period.findData(ui.get("totalPeriod", "today"))
        self.total_period.setCurrentIndex(max(0, total_index))
        average_index = self.average_period.findData(ui.get("averagePeriod", "today"))
        self.average_period.setCurrentIndex(max(0, average_index))
        position_index = self.overlay_position.findData(ui.get("overlayPosition", "top-right"))
        self.overlay_position.setCurrentIndex(max(0, position_index))
        self.overlay_font_size.setValue(int(ui.get("overlayFontSize", 12)))

        self.analytics_enabled.setChecked(bool(analytics.get("enabled", False)))
        self.mark_slow_fast.setChecked(bool(analytics.get("markSlowFast", False)))
        self.slow_percentile.setValue(int(analytics.get("slowPercentile", 75)))
        self.fast_percentile.setValue(int(analytics.get("fastPercentile", 25)))

        self.adaptive_enabled.setChecked(bool(adaptive.get("enabled", False)))
        self.adaptive_factor.setValue(float(adaptive.get("factor", 0.97)))
        self.adaptive_window.setValue(int(adaptive.get("windowDays", 30)))
        self.adaptive_floor.setValue(float(adaptive.get("floor", 1.0)))

        self._update_class_tabs()
        self._update_analytics_controls()

    def _update_class_tabs(self) -> None:
        for card_class, tab in self.class_tabs.items():
            index = self.tabs.indexOf(tab)
            if index < 0:
                continue
            disabled = False
            suffix = ""
            if card_class == "learning" and self.collapse_new_learning.isChecked():
                disabled = True
                suffix = " (uses New)"
            elif card_class == "relearning" and self.collapse_review_relearning.isChecked():
                disabled = True
                suffix = " (uses Review)"
            self.tabs.setTabEnabled(index, not disabled)
            self.tabs.setTabText(index, CLASS_LABELS[card_class] + suffix)
            self.tabs.setTabToolTip(
                index,
                "This class is collapsed into another tab." if disabled else "",
            )

    def _update_analytics_controls(self) -> None:
        analytics_on = self.analytics_enabled.isChecked()
        self.mark_slow_fast.setEnabled(analytics_on)
        self.slow_percentile.setEnabled(analytics_on)
        self.fast_percentile.setEnabled(analytics_on)

        self.adaptive_enabled.setEnabled(analytics_on)
        adaptive_on = analytics_on and self.adaptive_enabled.isChecked()
        self.adaptive_factor.setEnabled(adaptive_on)
        self.adaptive_window.setEnabled(adaptive_on)
        self.adaptive_floor.setEnabled(adaptive_on)

    def _restore_defaults(self) -> None:
        self._load_config(default_global_settings())
        tooltip("Defaults restored. Click OK to save.")

    def _test_alert_sound(self) -> None:
        path = _resolve_sound(self.alert_sound.currentText())
        try:
            av_player.clear_queue_and_maybe_interrupt()
            av_player.play_file(path)
        except Exception:
            tooltip("Could not play the alert sound.")

    def _open_user_files(self) -> None:
        os.makedirs(PATH_USERFILES, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(PATH_USERFILES))

    def result_config(self) -> dict[str, Any]:
        config = deepcopy(get_config())
        current_ui = config.get("ui", {})

        config["enabled"] = self.enabled.isChecked()
        config["suppressBuiltInAutoAdvance"] = self.suppress_builtin.isChecked()
        config["stopTimersWhenTyping"] = self.stop_typing.isChecked()
        config["alertSound"] = self.alert_sound.currentText().strip() or "default"
        config["moreTime"] = {
            "showButton": self.show_more_time.isChecked(),
            "hotkey": self.hotkey.keySequence().toString().strip() or "p",
        }
        config["grouping"] = {
            "collapseNewLearning": self.collapse_new_learning.isChecked(),
            "collapseReviewRelearning": self.collapse_review_relearning.isChecked(),
        }
        config["defaults"] = {
            card_class: self.class_tabs[card_class].dump() for card_class in CARD_CLASSES
        }
        config["ui"] = {
            "showCountdown": self.show_countdown.isChecked(),
            "showAverage": self.show_average.isChecked(),
            "showDeckTotal": self.show_deck_total.isChecked(),
            "showOverallTotal": self.show_overall_total.isChecked(),
            "totalPeriod": self.total_period.currentData(),
            "averagePeriod": self.average_period.currentData(),
            "overlayPosition": self.overlay_position.currentData(),
            "overlayFontSize": self.overlay_font_size.value(),
            "overlayXPercent": float(current_ui.get("overlayXPercent", 70.0)),
            "overlayYPercent": float(current_ui.get("overlayYPercent", 8.0)),
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
