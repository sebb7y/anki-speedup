import importlib.util
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parent.parent / "src" / "speedup" / "settings_schema.py"
_spec = importlib.util.spec_from_file_location("settings_schema", _MODULE_PATH)
assert _spec and _spec.loader
schema = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(schema)

apply_adaptive = schema.apply_adaptive
card_class_for = schema.card_class_for
deep_merge = schema.deep_merge
default_global_settings = schema.default_global_settings
effective_settings = schema.effective_settings
has_any_timer = schema.has_any_timer
normalize_class_settings = schema.normalize_class_settings
normalize_global_settings = schema.normalize_global_settings
recommend_settings = schema.recommend_settings


def test_deep_merge_preserves_untouched_keys():
    base = {"a": {"x": 1, "y": 2}, "b": 3}
    override = {"a": {"y": 5}}
    merged = deep_merge(base, override)
    assert merged == {"a": {"x": 1, "y": 5}, "b": 3}
    assert base["a"]["y"] == 2


def test_card_class_for_collapses_learning():
    assert card_class_for(1, {}) == "learning"
    assert card_class_for(1, {"collapseNewLearning": True}) == "new"
    assert card_class_for(3, {"collapseReviewRelearning": True}) == "review"
    assert card_class_for(2, {}) == "review"


def test_effective_settings_applies_deck_override():
    config = default_global_settings()
    config["defaults"]["review"]["question"]["revealAfter"] = 4.0
    override = {"review": {"question": {"revealAfter": 2.7}}}
    settings = effective_settings(config, override, card_type=2)
    assert settings["question"]["revealAfter"] == 2.7
    assert settings["cardClass"] == "review"


def test_effective_settings_enabled_flag():
    config = default_global_settings()
    assert effective_settings(config, {}, 2)["enabled"] is True
    assert effective_settings(config, {"enabled": False}, 2)["enabled"] is False


def test_global_switch_cannot_be_overridden_by_deck():
    config = default_global_settings()
    config["enabled"] = False
    override = {"enabled": True}
    assert effective_settings(config, override, 2)["enabled"] is False


def test_has_any_timer():
    settings = effective_settings(default_global_settings(), {}, 2)
    assert has_any_timer(settings) is False
    settings["question"]["revealAfter"] = 1.5
    assert has_any_timer(settings) is True


def test_normalize_class_settings_clamps_and_repairs_values():
    raw = {
        "question": {
            "alertAfter": "-2",
            "revealAfter": "not a number",
            "autoAction": {"after": 3, "action": "nope"},
        },
        "answer": "bad",
    }
    normalized = normalize_class_settings(raw)
    assert normalized["question"]["alertAfter"] == 0.0
    assert normalized["question"]["revealAfter"] == 0.0
    assert normalized["question"]["autoAction"] == {"after": 3.0, "action": "again"}
    assert normalized["answer"]["autoAction"]["action"] == "good"


def test_normalize_global_settings_keeps_values_in_range():
    config = normalize_global_settings(
        {
            "ui": {"overlayFontSize": 999, "overlayPosition": "middle"},
            "analytics": {"slowPercentile": 5, "fastPercentile": 99},
            "adaptive": {"factor": 3.0, "windowDays": 0},
        }
    )
    assert config["ui"]["overlayFontSize"] == 48
    assert config["ui"]["overlayPosition"] == "top-right"
    assert config["analytics"]["slowPercentile"] == 50
    assert config["analytics"]["fastPercentile"] == 50
    assert config["adaptive"]["factor"] == 1.0
    assert config["adaptive"]["windowDays"] == 1


def test_normalize_global_settings_uses_defaults_for_missing_data():
    config = normalize_global_settings({"enabled": "false"})
    assert config["enabled"] is True
    assert config["moreTime"] == {"showButton": False, "hotkey": "p"}
    assert set(config["defaults"]) == {"new", "learning", "review", "relearning"}


def test_recommend_settings():
    rec = recommend_settings(3.0, 4.0, factor=1.0, alert_lead=0.5)
    assert rec["question"]["revealAfter"] == 3.0
    assert rec["question"]["alertAfter"] == 2.5
    assert rec["answer"]["autoAction"]["after"] == 4.0


def test_apply_adaptive_replaces_enabled_timers():
    settings = effective_settings(default_global_settings(), {}, 2)
    settings["question"]["revealAfter"] = 10.0
    settings["answer"]["autoAction"]["after"] = 10.0
    adaptive = apply_adaptive(settings, 4.0, 5.0, factor=0.5, floor=1.0)
    assert adaptive["question"]["revealAfter"] == 2.0
    assert adaptive["answer"]["autoAction"]["after"] == 2.5
    assert adaptive["question"]["alertAfter"] == 0.0
