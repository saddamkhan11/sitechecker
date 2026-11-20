import pytest

from calculator.calc import default_plan
from plans.plan_checks import check_plan, clean_plan


def ids(findings, level=None):
    return {f["rule_id"] for f in findings if level is None or f["level"] == level}


def test_default_plan_passes():
    f = check_plan(default_plan(14, 12))
    assert [x["level"] for x in f] == ["ok"]


def test_small_room_and_no_window():
    plan = {"length_in": 84, "width_in": 84, "wall_in": 9,
            "openings": [{"id": "d1", "type": "door", "wall": "S", "offset_in": 24, "width_in": 36, "height_in": 84}]}
    f = check_plan(plan)
    assert "PLAN-01" in ids(f, "warn")  # 49 sq ft < 80
    assert "PLAN-03" in ids(f, "warn")  # no window area
    assert "PLAN-05" not in ids(f)      # 36/84 = 43% of the wall, under the 50% limit


def test_openings_rules():
    plan = {"length_in": 144, "width_in": 120, "wall_in": 9, "openings": [
        {"id": "d1", "type": "door", "wall": "S", "offset_in": 6, "width_in": 28, "height_in": 84},
        {"id": "w1", "type": "window", "wall": "S", "offset_in": 40, "width_in": 48, "height_in": 48},
        {"id": "w2", "type": "window", "wall": "N", "offset_in": 120, "width_in": 48, "height_in": 48},
    ]}
    f = check_plan(plan)
    assert "PLAN-02" in ids(f, "warn")   # d1 6 in from corner
    assert "PLAN-06" in ids(f, "warn")   # door 28 in < 30
    assert "PLAN-07" in ids(f, "warn")   # 6 in gap between d1 and w1
    assert "PLAN-05" in ids(f, "warn")   # 76/144 = 53% of south wall
    assert "PLAN-02" in ids(f, "error")  # w2 goes past the end of the north wall


def test_scope_errors_for_big_room():
    f = check_plan(default_plan(22, 16))
    assert {"SCOPE-01", "SCOPE-02"} <= ids(f, "error")


def test_missing_door_is_an_error():
    plan = {"length_in": 144, "width_in": 120, "wall_in": 9, "openings": []}
    assert "PLAN-06" in ids(check_plan(plan), "error")


def test_rules_table_values_are_used():
    plan = default_plan(12, 10)
    assert "PLAN-01" in ids(check_plan(plan, {"PLAN-01": 150}), "warn")


def test_clean_plan_rejects_junk():
    with pytest.raises(ValueError):
        clean_plan({"length_in": 99999, "width_in": 120})
    p = clean_plan({"length_in": "144", "width_in": 120, "openings": [{"type": "hack", "wall": "Z", "offset_in": 30, "width_in": 40}]})
    assert p["openings"][0]["type"] == "window" and p["openings"][0]["wall"] == "S"
