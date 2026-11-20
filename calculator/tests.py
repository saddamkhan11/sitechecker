"""Calculator tests against one room worked out by hand.

Room: inside 12 ft x 10 ft, 9 in walls, NO openings (to keep the hand sums readable),
then a second case with one door. Constants are the DEFAULTS (same as the seeded Rules).

REPLACE / EXTEND these numbers with the engineer's or contractor's own hand
calculation of a real room (plan week 4). The code must match it within the
margin the engineer agrees.
"""
import math

import pytest

from calculator import calc

ROOM = {"length_in": 144, "width_in": 120, "wall_in": 9, "openings": []}


def approx(x, rel=1e-6):
    return pytest.approx(x, rel=rel)


# ---- Hand calculation (ft) ----
# Centre line of walls: 2 x (12 + 10) + 4 x 0.75 = 47 ft
CL = 47.0
# Foundation: trench 2.25 ft wide x 3 ft deep; PCC 0.25 ft; brickwork 1.125 ft wide x 2.75 ft high
PCC = 47 * 2.25 * 0.25                    # 26.4375 cft
FND_BRICK = 47 * 1.125 * 2.75             # 145.40625 cft
PLINTH_BRICK = 47 * 0.75 * 1.5            # 52.875 cft
DPC = 47 * 0.75 * 0.125                   # 4.40625 cft
WALL_BRICK = 47 * 0.75 * 10               # 352.5 cft
ALL_BRICK = FND_BRICK + PLINTH_BRICK + WALL_BRICK   # 550.78125 cft
BRICKS = ALL_BRICK * 13.5                 # 7435.55 nos before wastage
MORTAR_DRY = ALL_BRICK * 0.25 * 1.27      # 174.873 cft, mix 1:6
SLAB = 13.5 * 11.5 * (5 / 12)             # 64.6875 cft, mix 1:2:4
PLASTER_AREA = (2 * 22 * 10 + 12 * 10) + (2 * 22 + 8 * 0.75) * (10 + 1.5 + 5 / 12)  # 560 + 595.83 sq ft
PLASTER_DRY = PLASTER_AREA * (0.5 / 12) * 1.35      # mix 1:4

CEMENT_CFT = (MORTAR_DRY / 7 + PCC * 1.54 / 13 + DPC * 1.54 / 7 + SLAB * 1.54 / 7 + PLASTER_DRY / 5)
SAND_CFT = (MORTAR_DRY * 6 / 7 + PCC * 1.54 * 4 / 13 + DPC * 1.54 * 2 / 7 + SLAB * 1.54 * 2 / 7 + PLASTER_DRY * 4 / 5)
CRUSH_CFT = PCC * 1.54 * 8 / 13 + DPC * 1.54 * 4 / 7 + SLAB * 1.54 * 4 / 7
# Slab steel: slab 13.5 x 11.5 ft. Main 1/2" @ 6" across the short span: floor(13.5*12/6)+1 = 28 bars x 12.5 ft
# Distribution 3/8" @ 9": floor(11.5*12/9)+1 = 16 bars x 14.5 ft
STEEL = 28 * 12.5 * 0.303 + 16 * 14.5 * 0.171   # 145.722 kg


def test_volumes_match_hand_calculation():
    v = calc.calculate(ROOM)["volumes"]
    assert v["centre_line_ft"] == approx(CL)
    assert v["pcc_cft"] == round(PCC, 2)
    assert v["foundation_brickwork_cft"] == round(FND_BRICK + PLINTH_BRICK, 2)
    assert v["dpc_cft"] == round(DPC, 2)
    assert v["wall_brickwork_cft"] == round(WALL_BRICK, 2)
    assert v["slab_concrete_cft"] == round(SLAB, 2)
    assert v["slab_main_bars"] == 28
    assert v["slab_distribution_bars"] == 16
    assert v["plaster_area_sqft"] == round(PLASTER_AREA, 1)


def test_materials_match_hand_calculation_with_wastage():
    m = calc.calculate(ROOM)["materials"]
    assert m["brick"] == math.ceil(BRICKS * 1.05)          # 7808
    assert m["cement"] == math.ceil(CEMENT_CFT / 1.25 * 1.03)
    assert m["sand"] == math.ceil(SAND_CFT * 1.05)
    assert m["crush"] == math.ceil(CRUSH_CFT * 1.05)
    assert m["steel"] == math.ceil(STEEL * 1.05)            # 154


def test_known_round_numbers():
    """Spot values a contractor can check on paper."""
    m = calc.calculate(ROOM)["materials"]
    assert m["brick"] == 7808
    assert m["steel"] == 154
    assert 44 <= m["cement"] <= 50


def test_door_reduces_bricks_and_adds_lintel():
    door = {**ROOM, "openings": [{"id": "d1", "type": "door", "wall": "S", "offset_in": 54, "width_in": 36, "height_in": 84}]}
    a, b = calc.calculate(ROOM), calc.calculate(door)
    # Door 3 x 7 ft = 21 sq ft x 0.75 = 15.75 cft; lintel (3 + 2 x 8/12) x 0.75 x 0.5 = 1.625 cft
    expected_wall = WALL_BRICK - 15.75 - (3 + 16 / 12) * 0.75 * 0.5
    assert b["volumes"]["wall_brickwork_cft"] == round(expected_wall, 2)
    assert b["volumes"]["lintel_concrete_cft"] == round((3 + 16 / 12) * 0.75 * 0.5, 2)
    assert b["materials"]["brick"] < a["materials"]["brick"]
    # lintel steel: 4 bars x 4.333 ft x 0.171 kg/ft = 2.964 kg before wastage
    assert b["sections"]["walls"]["steel"] == round(4 * (3 + 16 / 12) * 0.171, 2)


def test_constants_from_rules_table_change_the_result():
    more_waste = calc.calculate(ROOM, {"CALC-WASTE-BRICK": 10})
    assert more_waste["materials"]["brick"] == math.ceil(BRICKS * 1.10)


def test_bad_plan_is_rejected():
    with pytest.raises(calc.PlanError):
        calc.calculate({"length_in": 0, "width_in": 120})
    with pytest.raises(calc.PlanError):
        calc.calculate({"width_in": 120})


def test_cost_and_missing_rates():
    m = {"brick": 8000, "cement": 50, "sand": 300, "crush": 150, "steel": 160}
    c = calc.cost(m, {"brick": 18000, "cement": 1400})
    assert c["lines"]["brick"] == 144000          # 8 x 18000 (brick rate is per 1000)
    assert c["lines"]["cement"] == 70000
    assert c["total"] == 214000
    assert set(c["missing"]) == {"sand", "crush", "steel"}


def test_mistri_comparison():
    out = calc.compare_demand({"brick": 8000, "cement": 50}, {"brick": 9200, "cement": 50})
    assert out["brick"]["diff_pct"] == 15.0 and out["brick"]["flag"] is True
    assert out["cement"]["diff_pct"] == 0.0 and out["cement"]["flag"] is False


def test_default_plan_has_a_door():
    p = calc.default_plan(14, 12)
    assert p["length_in"] == 168 and p["width_in"] == 144
    assert any(o["type"] == "door" for o in p["openings"])


def test_brick_price_typed_per_brick_is_read_per_1000(db):
    from projects.models import Rate

    r = Rate.objects.create(material="brick", price=18, city="Karachi")
    assert r.price == 18000  # saved per 1000
    Rate.objects.filter(pk=r.pk).update(price=10)  # an old row saved before this rule
    assert Rate.objects.get(pk=r.pk).effective_price == 10000
