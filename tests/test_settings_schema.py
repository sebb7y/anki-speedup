import importlib.util
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parent.parent / "src" / "speedup" / "settings_schema.py"
_spec = importlib.util.spec_from_file_location("settings_schema", _MODULE_PATH)
assert _spec and _spec.loader
schema = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(schema)

card_class_for = schema.card_class_for
deep_merge = schema.deep_merge
default_global_settings = schema.default_global_settings
effective_settings = schema.effective_settings
has_any_timer = schema.has_any_timer
recommend_settings = schema.recommend_settings
scale_times = schema.scale_times


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


def test_has_any_timer():
    settings = effective_settings(default_global_settings(), {}, 2)
    assert has_any_timer(settings) is False
    settings["question"]["revealAfter"] = 1.5
    assert has_any_timer(settings) is True


def test_scale_times_respects_floor_and_zero():
    settings = effective_settings(default_global_settings(), {}, 2)
    settings["question"]["revealAfter"] = 10.0
    settings["answer"]["autoAction"]["after"] = 5.0
    scaled = scale_times(settings, factor=0.5, floor=4.0)
    assert scaled["question"]["revealAfter"] == 5.0
    assert scaled["answer"]["autoAction"]["after"] == 4.0
    assert scaled["question"]["alertAfter"] == 0.0


def test_recommend_settings():
    rec = recommend_settings(3.0, 4.0, factor=1.0, alert_lead=0.5)
    assert rec["question"]["revealAfter"] == 3.0
    assert rec["question"]["alertAfter"] == 2.5
    assert rec["answer"]["autoAction"]["after"] == 4.0
