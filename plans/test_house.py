"""Multi-room (house / washroom / kitchen) geometry, layout, checks and quantities."""
import pytest

from calculator import calc
from plans import geometry as g
from plans.layout import auto_layout, plot_from_area, room_spec
from plans.plan_checks import check_plan


def two_rooms():
    # Two 10 x 10 ft rooms side by side sharing one 9 in wall.
    return {"format": 2, "wall_in": 9, "plot": None, "rooms": [
        {"id": "r1", "name": "A", "type": "bedroom", "x_in": 9, "y_in": 9, "length_in": 120, "width_in": 120},
        {"id": "r2", "name": "B", "type": "bedroom", "x_in": 138, "y_in": 9, "length_in": 120, "width_in": 120},
    ], "openings": []}


def test_shared_wall_counted_once():
    p = two_rooms()
    # Hand calc (centre lines, ft): outer line 21.5 x 10.75 -> 2 x (21.5 + 10.75) = 64.5, plus the shared middle wall 10.75
    assert g.centre_line_length(p) / 12 == pytest.approx(75.25)
    area, perim, _ = g.footprint(p)
    assert area / 144 == pytest.approx((258 + 9) * (138) / 144)  # 22.25 x 11.5 ft outside
    assert perim / 12 == pytest.approx(2 * (22.25 + 11.5))
    assert g.neighbour_across(p, p["rooms"][0], "E")["id"] == "r2"
    assert g.free_ranges(p, p["rooms"][0], "E") == []
    assert g.free_ranges(p, p["rooms"][0], "N") == [(0.0, 120.0)]


def test_two_rooms_cost_less_than_two_separate_rooms():
    one = {"length_in": 120, "width_in": 120, "wall_in": 9, "openings": []}
    single = calc.calculate(one)["materials"]["brick"]
    joined = calc.calculate(two_rooms())["materials"]["brick"]
    assert single < joined < 2 * single


def test_single_room_v1_and_v2_give_same_quantities():
    v1 = {"length_in": 144, "width_in": 120, "wall_in": 9, "openings": []}
    assert calc.calculate(v1)["materials"] == calc.calculate(g.normalize(v1))["materials"]


def test_layout_for_a_small_house_fits_the_plot_and_is_clean():
    plot = {"length_in": 30 * 12, "width_in": 60 * 12}
    specs = [room_spec("Bed 1", "bedroom"), room_spec("Bed 2", "bedroom"), room_spec(None, "living"),
             room_spec(None, "kitchen"), room_spec(None, "washroom")]
    p = auto_layout(specs, plot)
    assert len(p["rooms"]) == 5
    assert g.overlaps(p) == []
    rooms = g.room_map(p)
    for room in p["rooms"]:
        doors = [o for o in p["openings"] if o["room"] == room["id"] and o["type"] == "door"]
        assert doors, room["name"]
        for o in p["openings"]:
            if o["room"] == room["id"] and o["type"] == "window":
                assert g.opening_target(p, rooms[o["room"]], o) == "outside"
    errors = [f for f in check_plan(p) if f["level"] == "error"]
    assert errors == []


def test_single_washroom():
    p = auto_layout([room_spec(None, "washroom", 5, 7)])
    f = check_plan(p)
    assert [x for x in f if x["level"] == "error"] == []
    assert not any(x["rule_id"] == "PLAN-08" for x in f)  # ventilator was placed
    q = calc.calculate(p)["materials"]
    assert q["brick"] > 0 and q["cement"] > 0


def test_washroom_without_ventilator_is_flagged():
    p = auto_layout([room_spec(None, "washroom", 5, 7)])
    p["openings"] = [o for o in p["openings"] if o["type"] == "door"]
    assert any(x["rule_id"] == "PLAN-08" for x in check_plan(p))


def test_scope_limits_for_big_house():
    specs = [room_spec(f"Bed {i}", "bedroom", 14, 14) for i in range(9)]
    f = check_plan(auto_layout(specs))
    ids = {x["rule_id"] for x in f if x["level"] == "error"}
    assert "SCOPE-12" in ids and "SCOPE-11" in ids


def test_room_outside_plot_and_overlap():
    p = two_rooms()
    p["plot"] = {"length_in": 200, "width_in": 200}
    p["rooms"][1]["x_in"] = 120  # inside the first room's wall
    ids = {x["rule_id"] for x in check_plan(p) if x["level"] == "error"}
    assert {"PLOT-01", "PLAN-09"} <= ids


def test_odd_gap_between_rooms():
    p = two_rooms()
    p["rooms"][1]["x_in"] = 138 + 12  # 12 in gap + wall
    assert any(x["rule_id"] == "PLAN-09" and x["level"] == "warn" for x in check_plan(p))


R = room_spec
BRIEFS = {
    "room 12x14": ([R(None, "room", 14, 12)], None),
    "washroom 5x7": ([R(None, "washroom", 7, 5)], None),
    "kitchen + washroom": ([R(None, "kitchen"), R(None, "washroom")], None),
    "3 marla, 1 bed": ([R(None, "bedroom"), R(None, "kitchen"), R(None, "washroom")], plot_from_area(3 * 225)),
    "5 marla, 2 bed": ([R("Bedroom 1", "bedroom"), R("Bedroom 2", "bedroom"), R(None, "living"), R(None, "kitchen"),
                        R("Washroom 1", "washroom"), R("Washroom 2", "washroom")], plot_from_area(5 * 225)),
    "30x60, 2 bed 2 wash": ([R("Bedroom 1", "bedroom", 13, 12), R("Bedroom 2", "bedroom"), R(None, "store"), R(None, "kitchen"),
                             R("Washroom 1", "washroom"), R("Washroom 2", "washroom")], {"length_in": 360, "width_in": 720}),
    "120 gaz, 3 bed": ([R(f"Bedroom {i}", "bedroom") for i in (1, 2, 3)] + [R(None, "living"), R(None, "kitchen"),
                        R("Washroom 1", "washroom"), R("Washroom 2", "washroom")], plot_from_area(120 * 9)),
}


@pytest.mark.parametrize("name", list(BRIEFS))
def test_typical_briefs_have_no_plan_problems(name):
    specs, plot = BRIEFS[name]
    p = auto_layout(specs, plot)
    problems = [f for f in check_plan(p) if f["level"] != "ok"]
    assert problems == [], [f["en"] for f in problems]
    # every washroom has a ventilator on an outside wall, every room a door
    rooms = g.room_map(p)
    for r in p["rooms"]:
        assert any(o["room"] == r["id"] and o["type"] == "door" for o in p["openings"]) or \
            any(o["type"] == "door" and g.opening_target(p, rooms[o["room"]], o) == r["id"] for o in p["openings"])
        if r["type"] == "washroom":
            assert any(o["room"] == r["id"] and o["type"] == "window" and g.opening_target(p, r, o) == "outside"
                       for o in p["openings"])


def test_layout_is_repeatable():
    specs, plot = BRIEFS["5 marla, 2 bed"]
    assert auto_layout(specs, plot) == auto_layout(specs, plot)


def test_user_sizes_are_kept_default_sizes_may_flex():
    specs, plot = BRIEFS["30x60, 2 bed 2 wash"]
    p = auto_layout(specs, plot)
    b1 = next(r for r in p["rooms"] if r["name"] == "Bedroom 1")
    assert sorted([b1["length_in"], b1["width_in"]]) == [144, 156]  # 13 x 12 as asked


def test_window_meets_light_rule_for_big_room():
    p = auto_layout([R(None, "living", 14, 13)])
    assert not [f for f in check_plan(p) if f["rule_id"] == "PLAN-03"]


def test_plot_from_marla_area():
    plot = plot_from_area(5 * 225)
    assert abs(plot["length_in"] * plot["width_in"] / 144 - 1125) < 40
