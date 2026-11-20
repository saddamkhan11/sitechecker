"""Material calculator for one single-storey brick room with an RCC slab.

Pure Python: no Django, no AI. The AI calls this as a tool and never does
arithmetic itself. Every constant comes from the Rules table (passed in as
``constants``); DEFAULTS are only used when a rule is missing.

Plan JSON (all sizes in inches, inner clear dimensions):
    {"length_in": 144, "width_in": 120, "wall_in": 9,
     "openings": [{"id": "d1", "type": "door", "wall": "S", "offset_in": 30,
                   "width_in": 36, "height_in": 84}]}
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from plans import geometry

DEFAULTS = {
    "WALL-01": 9,  # wall thickness, in
    "FND-01": 36,  # trench depth, in
    "FND-02": 27,  # trench width, in
    "FND-03": 3,  # PCC thickness, in
    "FND-04": 13.5,  # foundation brickwork width, in
    "PLN-01": 18,  # plinth height, in
    "PLN-02": 1.5,  # DPC thickness, in
    "OPN-01": 8,  # lintel bearing each side, in
    "OPN-02": 6,  # lintel depth, in
    "SST-01": 6,  # main bar spacing, in
    "SST-02": 9,  # distribution bar spacing, in
    "SLB-01": 5,  # slab thickness, in
    "PLS-01": 0.5,  # plaster thickness, in
    "CALC-WALL-HEIGHT": 10,  # ft
    "CALC-BRICKS-PER-CFT": 13.5,
    "CALC-MORTAR-WET": 0.25,
    "CALC-DRY-MORTAR": 1.27,
    "CALC-DRY-CONCRETE": 1.54,
    "CALC-CEMENT-BAG-CFT": 1.25,
    "CALC-MORTAR-SAND": 6,
    "CALC-PLASTER-SAND": 4,
    "CALC-PLASTER-FACTOR": 1.35,
    "CALC-RCC-SAND": 2,
    "CALC-RCC-CRUSH": 4,
    "CALC-PCC-SAND": 4,
    "CALC-PCC-CRUSH": 8,
    "CALC-STEEL-12MM-KGFT": 0.303,
    "CALC-STEEL-10MM-KGFT": 0.171,
    "CALC-STEEL-EXTRA-FT": 1,
    "CALC-WASTE-BRICK": 5,
    "CALC-WASTE-CEMENT": 3,
    "CALC-WASTE-SAND": 5,
    "CALC-WASTE-CRUSH": 5,
    "CALC-WASTE-STEEL": 5,
    "CALC-MISTRI-TOLERANCE": 10,
}

LINTEL_BARS = 4  # 2 top + 2 bottom, 3/8 inch (rule OPN-02)
MATERIALS = ["brick", "cement", "sand", "crush", "steel"]
UNITS = {"brick": "nos", "cement": "bags", "sand": "cft", "crush": "cft", "steel": "kg"}


class PlanError(ValueError):
    pass


@dataclass
class Mix:
    """Dry materials for one part of the work, before wastage."""

    bricks: float = 0.0
    cement_cft: float = 0.0
    sand_cft: float = 0.0
    crush_cft: float = 0.0
    steel_kg: float = 0.0

    def add(self, other: "Mix") -> "Mix":
        return Mix(*(a + b for a, b in zip(self.astuple(), other.astuple())))

    def astuple(self):
        return (self.bricks, self.cement_cft, self.sand_cft, self.crush_cft, self.steel_kg)


@dataclass
class Result:
    volumes: dict = field(default_factory=dict)
    sections: dict = field(default_factory=dict)
    materials: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)

    def as_dict(self):
        return {"volumes": self.volumes, "sections": self.sections, "materials": self.materials,
                "units": UNITS, "notes": self.notes}


def _concrete(volume_cft, sand_parts, crush_parts, c) -> Mix:
    dry = volume_cft * c["CALC-DRY-CONCRETE"]
    total = 1 + sand_parts + crush_parts
    return Mix(cement_cft=dry / total, sand_cft=dry * sand_parts / total, crush_cft=dry * crush_parts / total)


def _mortar_dry(dry_cft, sand_parts) -> Mix:
    total = 1 + sand_parts
    return Mix(cement_cft=dry_cft / total, sand_cft=dry_cft * sand_parts / total)


def _brickwork(volume_cft, c) -> Mix:
    dry = volume_cft * c["CALC-MORTAR-WET"] * c["CALC-DRY-MORTAR"]
    m = _mortar_dry(dry, c["CALC-MORTAR-SAND"])
    m.bricks = volume_cft * c["CALC-BRICKS-PER-CFT"]
    return m


def validate_plan(plan: dict) -> dict:
    """Check numbers and return the plan in format 2 (any number of rooms)."""
    try:
        p = geometry.normalize(plan)
        for r in p["rooms"]:
            if float(r["length_in"]) <= 0 or float(r["width_in"]) <= 0:
                raise PlanError(f"Room {r.get('name', r.get('id'))} needs a length and width more than zero.")
    except (KeyError, TypeError, ValueError) as e:
        if isinstance(e, PlanError):
            raise
        raise PlanError("Plan needs room sizes (length_in and width_in) as numbers.")
    if not p["rooms"]:
        raise PlanError("Plan has no rooms.")
    for o in p.get("openings", []):
        if float(o.get("width_in", 0)) <= 0 or float(o.get("height_in", 0)) <= 0:
            raise PlanError(f"Opening {o.get('id', '?')} needs a width and height.")
    return p


def calculate(plan: dict, constants: dict | None = None) -> dict:
    """Return volumes, a per-section breakdown and the material list (with wastage, rounded up).

    Works for one room or a whole single-storey house: walls shared by two rooms are counted once.
    """
    p = validate_plan(plan)
    c = {**DEFAULTS, **{k: v for k, v in (constants or {}).items() if v is not None}}
    if not plan.get("wall_in") and "WALL-01" in c:
        p["wall_in"] = c["WALL-01"]

    t = float(p["wall_in"]) / 12
    H = c["CALC-WALL-HEIGHT"]
    openings = p.get("openings", [])
    rooms = geometry.room_map(p)
    res = Result()

    centre_line = geometry.centre_line_length(p) / 12  # every wall once, ft
    fp_area_in, fp_perim_in, _ = geometry.footprint(p)

    # --- Foundation ---
    depth = c["FND-01"] / 12
    trench_w = c["FND-02"] / 12
    pcc_t = c["FND-03"] / 12
    excavation = centre_line * trench_w * depth
    pcc = centre_line * trench_w * pcc_t
    fnd_brick = centre_line * (c["FND-04"] / 12) * (depth - pcc_t)
    plinth_brick = centre_line * t * (c["PLN-01"] / 12)
    dpc = centre_line * t * (c["PLN-02"] / 12)
    foundation = (
        _concrete(pcc, c["CALC-PCC-SAND"], c["CALC-PCC-CRUSH"], c)
        .add(_brickwork(fnd_brick + plinth_brick, c))
        .add(_concrete(dpc, c["CALC-RCC-SAND"], c["CALC-RCC-CRUSH"], c))
    )

    # --- Walls and lintels ---
    open_area = sum(float(o["width_in"]) * float(o["height_in"]) for o in openings) / 144  # sq ft
    bearing = c["OPN-01"] / 12
    lintel_d = c["OPN-02"] / 12
    lintel_lengths = [float(o["width_in"]) / 12 + 2 * bearing for o in openings]
    lintel_vol = sum(ll * t * lintel_d for ll in lintel_lengths)
    wall_brick = centre_line * t * H - open_area * t - lintel_vol
    walls = _brickwork(wall_brick, c)
    lintels = _concrete(lintel_vol, c["CALC-RCC-SAND"], c["CALC-RCC-CRUSH"], c)
    lintels.steel_kg = sum(ll * LINTEL_BARS for ll in lintel_lengths) * c["CALC-STEEL-10MM-KGFT"]

    # --- Slab: one slab over the whole footprint; steel worked out per room panel ---
    slab_t = c["SLB-01"] / 12
    slab_vol = fp_area_in / 144 * slab_t
    slab = _concrete(slab_vol, c["CALC-RCC-SAND"], c["CALC-RCC-CRUSH"], c)
    extra = c["CALC-STEEL-EXTRA-FT"]
    n_main = n_dist = 0
    main_ft = dist_ft = 0.0
    for r in p["rooms"]:
        a, b = float(r["length_in"]) / 12 + 2 * t, float(r["width_in"]) / 12 + 2 * t  # panel rests on full walls
        short, long_ = sorted([a, b])
        nm = math.floor(long_ * 12 / c["SST-01"]) + 1  # main bars span the short side
        nd = math.floor(short * 12 / c["SST-02"]) + 1
        n_main, n_dist = n_main + nm, n_dist + nd
        main_ft += nm * (short + extra)
        dist_ft += nd * (long_ + extra)
    slab.steel_kg = main_ft * c["CALC-STEEL-12MM-KGFT"] + dist_ft * c["CALC-STEEL-10MM-KGFT"]

    # --- Plaster: inside every room + ceilings, outside face of the building incl. plinth and slab edge ---
    inside = 0.0
    for r in p["rooms"]:
        L, W = float(r["length_in"]) / 12, float(r["width_in"]) / 12
        own_open = sum(float(o["width_in"]) * float(o["height_in"]) for o in openings if o.get("room") == r["id"]) / 144
        inside += 2 * (L + W) * H - own_open + L * W
    ext_open = sum(float(o["width_in"]) * float(o["height_in"]) for o in openings
                   if o.get("room") in rooms and geometry.opening_exterior(p, rooms[o["room"]], o)) / 144
    outside = fp_perim_in / 12 * (H + c["PLN-01"] / 12 + slab_t) - ext_open
    plaster_area = inside + outside
    plaster_vol = plaster_area * c["PLS-01"] / 12
    plaster = _mortar_dry(plaster_vol * c["CALC-PLASTER-FACTOR"], c["CALC-PLASTER-SAND"])

    res.volumes = {
        "centre_line_ft": round(centre_line, 3),
        "excavation_cft": round(excavation, 2),
        "pcc_cft": round(pcc, 2),
        "foundation_brickwork_cft": round(fnd_brick + plinth_brick, 2),
        "dpc_cft": round(dpc, 2),
        "wall_brickwork_cft": round(wall_brick, 2),
        "lintel_concrete_cft": round(lintel_vol, 2),
        "slab_concrete_cft": round(slab_vol, 2),
        "plaster_area_sqft": round(plaster_area, 1),
        "slab_main_bars": n_main,
        "slab_distribution_bars": n_dist,
    }

    parts = {"foundation": foundation, "walls": walls.add(lintels), "slab": slab, "plaster": plaster}
    bag = c["CALC-CEMENT-BAG-CFT"]
    for name, m in parts.items():
        res.sections[name] = {
            "brick": round(m.bricks), "cement": round(m.cement_cft / bag, 2), "sand": round(m.sand_cft, 2),
            "crush": round(m.crush_cft, 2), "steel": round(m.steel_kg, 2),
        }

    total = Mix()
    for m in parts.values():
        total = total.add(m)

    def w(v, key):
        return v * (1 + c[key] / 100)

    res.materials = {
        "brick": math.ceil(w(total.bricks, "CALC-WASTE-BRICK")),
        "cement": math.ceil(w(total.cement_cft / bag, "CALC-WASTE-CEMENT")),
        "sand": math.ceil(w(total.sand_cft, "CALC-WASTE-SAND")),
        "crush": math.ceil(w(total.crush_cft, "CALC-WASTE-CRUSH")),
        "steel": math.ceil(w(total.steel_kg, "CALC-WASTE-STEEL")),
    }
    res.volumes["rooms"] = len(p["rooms"])
    res.volumes["covered_area_sqft"] = round(fp_area_in / 144, 1)
    res.notes = [
        "Quantities include wastage from the Rules table and are rounded up.",
        "Walls shared by two rooms are counted once.",
        "Excavation is shown for labour planning; it uses no material.",
        "Doors, windows, flooring, tiles, electrical and plumbing fittings are not included.",
    ]
    return res.as_dict()


def cost(materials: dict, rates: dict) -> dict:
    """rates: {material: price}. Brick price is per 1000. Missing rates are reported, not guessed."""
    lines, total, missing = {}, 0.0, []
    for mat in MATERIALS:
        qty = materials.get(mat, 0)
        price = rates.get(mat)
        if price is None:
            missing.append(mat)
            lines[mat] = None
            continue
        amount = qty / 1000 * float(price) if mat == "brick" else qty * float(price)
        lines[mat] = round(amount)
        total += amount
    return {"lines": lines, "total": round(total), "missing": missing}


def compare_demand(estimate: dict, demand: dict, tolerance_pct: float = DEFAULTS["CALC-MISTRI-TOLERANCE"]) -> dict:
    """Difference between the mistri's demand and the estimate, in percent per material."""
    out = {}
    for mat in MATERIALS:
        d = demand.get(mat)
        e = estimate.get(mat)
        if d in (None, "") or not e:
            continue
        pct = (float(d) - float(e)) / float(e) * 100
        out[mat] = {"estimate": e, "demand": float(d), "diff_pct": round(pct, 1), "flag": pct > tolerance_pct}
    return out


def default_plan(length_ft: float, width_ft: float, wall_in: float = 9) -> dict:
    """A starting plan: one door on the south wall and one window on each of north and east."""
    L, W = round(float(length_ft) * 12), round(float(width_ft) * 12)
    door_w, win_w = 36, 48
    return {
        "length_in": L,
        "width_in": W,
        "wall_in": wall_in,
        "openings": [
            {"id": "d1", "type": "door", "wall": "S", "offset_in": max(24, round((L - door_w) / 2)), "width_in": door_w, "height_in": 84},
            {"id": "w1", "type": "window", "wall": "N", "offset_in": max(24, round((L - win_w) / 2)), "width_in": win_w, "height_in": 48, "sill_in": 36},
            {"id": "w2", "type": "window", "wall": "E", "offset_in": max(24, round((W - win_w) / 2)), "width_in": win_w, "height_in": 48, "sill_in": 36},
        ],
    }
