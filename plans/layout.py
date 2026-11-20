"""Automatic layout: turn a list of rooms (and an optional plot) into a format-2 plan.

How it works (a first draft a person then adjusts, not an architect's design):
  1. Pack the rooms in rows that share walls, many times over with different orders and
     turns of the rooms (a small search).
  2. Close thin gaps: a room with a default size is stretched (or slid) to meet its neighbour,
     so there are no useless strips that collect dirt and water (rule PLAN-09).
  3. Doors and windows: every room gets a door; windows are sized from the light rule
     (PLAN-03, 10% of the floor) and washrooms get a ventilator on an outside wall (PLAN-08).
  4. Every candidate is scored with OUR plan checks (plans/plan_checks.py) and the best one wins.
     The front (bottom) of the plot is left open as a courtyard.
"""
from __future__ import annotations

import itertools
import math
import random

from .geometry import (ROOM_TYPES, WET_TYPES, footprint, free_ranges, neighbour_across, normalize, overlaps,
                       wall_length)

DOOR_W = {"washroom": 27, "store": 30, "kitchen": 33}
WINDOW_H = {"washroom": 18, "store": 18}  # small high ventilators
WINDOW_SILL = {"washroom": 60, "store": 60, "kitchen": 42}
CORNER = 24  # keep openings this far from inside corners (rule PLAN-02 default)
MIN_FLEX_SIDE = {"bedroom": 126, "living": 132, "room": 120, "kitchen": 84, "washroom": 54, "store": 54}  # inches
MAX_STRETCH = 30  # inches a default-size room may grow to close a gap
SEARCH = 220  # candidate layouts tried for 4+ rooms

# How much each problem costs when choosing between layouts.
PENALTY = {"error": 1000, "PLAN-08": 220, "PLAN-09": 160, "PLAN-06": 300, "PLAN-03": 40, "PLAN-02": 12, "PLAN-07": 12}


def room_spec(name=None, type="room", length_ft=None, width_ft=None):
    """A room to place. Without sizes it uses the type's default and may be resized a little to fit."""
    type = type if type in ROOM_TYPES else "room"
    d = ROOM_TYPES[type]
    L = float(length_ft or d[3]) * 12
    W = float(width_ft or d[4]) * 12
    return {"name": (name or d[0])[:30], "type": type, "length_in": max(L, W), "width_in": min(L, W),
            "flex": not (length_ft and width_ft)}


# ---------------------------------------------------------------- packing
def _pack(order, max_row, t, squeeze=True):
    """Rows of rooms side by side; each room sits right under whatever is above it (skyline)."""
    rows, cur = [], []

    def used(row):
        return sum(r["length_in"] for r in row) + t * max(0, len(row) - 1)

    for s in (dict(x) for x in order):
        if s["length_in"] > max_row and s["width_in"] <= max_row:
            s["length_in"], s["width_in"] = s["width_in"], s["length_in"]
        if cur:
            left = max_row - used(cur) - t
            if s["length_in"] <= left + 0.5:
                cur.append(s)
                continue
            if s["width_in"] <= left + 0.5:
                s["length_in"], s["width_in"] = s["width_in"], s["length_in"]
                cur.append(s)
                continue
            flex = [r for r in cur + [s] if r.get("flex")]
            short = used(cur + [s]) - max_row
            give = sum(max(0, r["length_in"] - MIN_FLEX_SIDE.get(r["type"], 96)) for r in flex)
            if squeeze and flex and 0 < short <= give:
                for r in flex:
                    can = max(0, r["length_in"] - MIN_FLEX_SIDE.get(r["type"], 96))
                    r["length_in"] = round(r["length_in"] - short * can / give - 0.5)
                cur.append(s)
                continue
            rows.append(cur)
            cur = []
        cur.append(s)
    if cur:
        rows.append(cur)

    rooms = []
    for row in rows:
        x = t
        for s in row:
            above = [r["y_in"] + r["width_in"] for r in rooms
                     if r["x_in"] < x + s["length_in"] - 0.5 and r["x_in"] + r["length_in"] > x + 0.5]
            y = (max(above) + t) if above else t
            rooms.append({"id": "", "name": s["name"], "type": s["type"], "x_in": round(x, 1), "y_in": round(y, 1),
                          "length_in": s["length_in"], "width_in": s["width_in"], "_flex": s.get("flex", False)})
            x += s["length_in"] + t
    for i, r in enumerate(rooms):
        r["id"] = f"r{i + 1}"
    return rooms


def _close_gaps(plan, passage=36):
    """Stretch a default-size room (or slide a room) to remove gaps thinner than a passage."""
    t = plan["wall_in"]
    span_limit = 14 * 12  # never stretch a room's short side past the SCOPE-01 default
    for _ in range(3):
        changed = False
        rooms = plan["rooms"]
        for a in rooms:
            for b in rooms:
                if a is b:
                    continue
                # b below a, overlapping in x
                ox = min(a["x_in"] + a["length_in"], b["x_in"] + b["length_in"]) - max(a["x_in"], b["x_in"])
                gap = b["y_in"] - (a["y_in"] + a["width_in"]) - t
                if ox > 12 and 0.5 < gap < passage:
                    if _try(plan, a, "width_in", gap, span_limit) or _try_move(plan, b, "y_in", -gap):
                        changed = True
                # b right of a, overlapping in y
                oy = min(a["y_in"] + a["width_in"], b["y_in"] + b["width_in"]) - max(a["y_in"], b["y_in"])
                gap = b["x_in"] - (a["x_in"] + a["length_in"]) - t
                if oy > 12 and 0.5 < gap < passage:
                    if _try(plan, a, "length_in", gap, span_limit) or _try_move(plan, b, "x_in", -gap):
                        changed = True
        if not changed:
            break


def _try(plan, room, key, amount, span_limit):
    if not room.get("_flex") or amount > MAX_STRETCH:
        return False
    old = room[key]
    room[key] = old + amount
    if overlaps(plan) or min(room["length_in"], room["width_in"]) > span_limit:
        room[key] = old
        return False
    return True


def _try_move(plan, room, key, amount):
    old = room[key]
    room[key] = old + amount
    if overlaps(plan) or room[key] < plan["wall_in"] - 0.5:
        room[key] = old
        return False
    return True


# ---------------------------------------------------------------- openings
def _new_id(plan, prefix):
    n = 1
    while any(x["id"] == f"{prefix}{n}" for x in plan["openings"]):
        n += 1
    return f"{prefix}{n}"


def _taken(plan, room, wall):
    return [(o["offset_in"], o["offset_in"] + o["width_in"]) for o in plan["openings"]
            if o.get("room") == room["id"] and o["wall"] == wall]


def _spot(rng, width, taken, wall_len, strict):
    """Offset for an opening inside free range rng, clear of corners (if strict) and other openings."""
    a, b = rng
    lo = max(a, CORNER) if strict else a
    hi = (min(b, wall_len - CORNER) if strict else b) - width
    if hi < lo - 0.01:
        return None
    mid = (lo + hi) / 2
    cands = sorted({round(mid), round(lo), round(hi)} | {round(t1 + 18) for _, t1 in taken} | {round(t0 - 18 - width) for t0, _ in taken},
                   key=lambda v: abs(v - mid))
    for start in cands:
        if lo - 0.5 <= start <= hi + 0.5 and all(start + width + 18 <= t0 or start >= t1 + 18 for t0, t1 in taken):
            return start
    return None


def place_opening(plan, room, kind, width, height, sill=None, walls=None, outside_only=False, min_width=None):
    """Put an opening on the best free spot. It is made narrower (down to min_width) before it is
    allowed near a corner. Returns the opening or None if nothing fits."""
    walls = walls or ("S", "E", "W", "N")
    min_width = min_width or (30 if kind == "door" else 18)
    passes = [(True, True), (True, False)] if outside_only else [(True, True), (False, True), (True, False), (False, False)]
    for want_outside, strict in passes:
        for wall in walls:
            wl = wall_length(room, wall)
            ranges = free_ranges(plan, room, wall) if want_outside else [(0.0, wl)]
            for rng in sorted(ranges, key=lambda r: -(r[1] - r[0])):
                w = width
                while w >= min_width - 0.01:
                    off = _spot(rng, w, _taken(plan, room, wall), wl, strict)
                    if off is not None and (want_outside or neighbour_across(plan, room, wall, off, off + w) is not None):
                        o = {"id": _new_id(plan, "d" if kind == "door" else "w"), "room": room["id"], "type": kind,
                             "wall": wall, "offset_in": off, "width_in": w, "height_in": height}
                        if kind == "window":
                            o["sill_in"] = 36 if sill is None else sill
                        plan["openings"].append(o)
                        return o
                    w -= 6
    return None


def _window_need(room, rules):
    """Window area (sq in) a room needs: 10% of floor for living spaces, a ventilator for washrooms."""
    r = rules or {}
    if room["type"] == "washroom":
        return float(r.get("PLAN-08", 1.5)) * 144
    if room["type"] == "store":
        return 0
    return room["length_in"] * room["width_in"] * float(r.get("PLAN-03", 10)) / 100


def add_default_openings(plan, rules=None):
    """A door for every room, then windows until the room has the window area the rules ask for."""
    for room in plan["rooms"]:
        mine = [o for o in plan["openings"] if o.get("room") == room["id"]]
        if not any(o["type"] == "door" for o in mine):
            place_opening(plan, room, "door", DOOR_W.get(room["type"], 36), 84,
                          min_width=24 if room["type"] in ("washroom", "store") else 30)
    for room in plan["rooms"]:
        need = _window_need(room, rules)
        h = WINDOW_H.get(room["type"], 48)
        have = sum(o["width_in"] * o["height_in"] for o in plan["openings"] if o.get("room") == room["id"] and o["type"] == "window")
        tries = 0
        while (have < need or (room["type"] == "store" and not have and tries == 0)) and tries < 3:
            width = min(72, max(24, math.ceil((need - have) / h / 6) * 6)) if need else 24
            o = place_opening(plan, room, "window", width, h, WINDOW_SILL.get(room["type"], 36),
                              walls=("N", "E", "W", "S"), outside_only=True, min_width=18)
            tries += 1
            if not o:
                break
            have += o["width_in"] * o["height_in"]
    return plan


# ---------------------------------------------------------------- search
def _score(plan, rules):
    from .plan_checks import check_plan

    s = 0.0
    for f in check_plan(plan, rules):
        if f["level"] == "error":
            s += PENALTY["error"]
        elif f["level"] == "warn":
            s += PENALTY.get(f["rule_id"], 8)
    area, perim, box = footprint(plan)
    s += perim / 120  # compact buildings need less outside plaster
    s += (box[3] - box[1]) / 60  # shallower building = bigger courtyard at the front
    # wet rooms sharing a wall keep pipes short
    rooms = plan["rooms"]
    wet = [r for r in rooms if r["type"] in WET_TYPES]
    for a, b in itertools.combinations(wet, 2):
        if any(neighbour_across(plan, a, w) is b or neighbour_across(plan, b, w) is a for w in ("N", "S", "E", "W")):
            s -= 6
    return s


def _orders(specs, rng):
    base = sorted(specs, key=lambda s: (s["type"] in WET_TYPES, -s["width_in"], -s["length_in"]))
    yield base
    yield sorted(specs, key=lambda s: (-s["length_in"] * s["width_in"]))
    yield sorted(specs, key=lambda s: (s["type"] not in WET_TYPES, -s["width_in"]))
    if len(specs) <= 4:
        for p in itertools.permutations(specs):
            yield list(p)
        return
    for _ in range(SEARCH):
        o = list(specs)
        rng.shuffle(o)
        yield o


def _build(order, plot, t, rules, rotate):
    order = [dict(s) for s in order]
    for s, r in zip(order, rotate):
        if r:
            s["length_in"], s["width_in"] = s["width_in"], s["length_in"]
    if plot:
        max_row = float(plot["length_in"]) - 2 * t
    else:
        total = sum(s["length_in"] * s["width_in"] for s in order)
        max_row = max(max(min(s["length_in"], s["width_in"]) for s in order), math.sqrt(total) * 1.4)
    plan = {"format": 2, "wall_in": t, "plot": plot, "rooms": _pack(order, max_row, t), "openings": []}
    _close_gaps(plan, float((rules or {}).get("PLAN-09", 36)))
    add_default_openings(plan, rules)
    return plan


def auto_layout(specs: list[dict], plot: dict | None = None, wall_in: float = 9, rules: dict | None = None,
                seed: int = 7) -> dict:
    """Best layout found for these rooms. Same input -> same output (seeded search)."""
    t = float(wall_in)
    if not specs:
        raise ValueError("At least one room is needed.")
    rng = random.Random(seed)
    best, best_score = None, float("inf")
    seen = set()
    for order in _orders(specs, rng):
        for attempt in range(2 if len(specs) > 1 else 1):
            rotate = [False] * len(order) if attempt == 0 else [rng.random() < 0.35 for _ in order]
            key = (tuple((s["name"], s["type"]) for s in order), tuple(rotate))
            if key in seen:
                continue
            seen.add(key)
            plan = _build(order, plot, t, rules, rotate)
            sc = _score(plan, rules)
            if sc < best_score:
                best, best_score = plan, sc
        if best_score < 5:  # nothing left to improve
            break
    for r in best["rooms"]:
        r.pop("_flex", None)
        r["length_in"], r["width_in"] = round(r["length_in"], 1), round(r["width_in"], 1)
    return best


def relayout(plan: dict, rules: dict | None = None) -> dict:
    """Re-pack an existing plan's rooms, keeping names, types and sizes. Doors and windows are placed again."""
    p = normalize(plan)
    specs = [{"name": r["name"], "type": r["type"], "length_in": r["length_in"], "width_in": r["width_in"], "flex": False}
             for r in p["rooms"]]
    return auto_layout(specs, p.get("plot"), p["wall_in"], rules)


def plot_from_area(area_sqft: float, ratio: float = 1.8) -> dict:
    """A plot of this area with front:depth = 1:ratio, in whole feet."""
    w = max(10, round(math.sqrt(area_sqft / ratio)))
    d = max(10, round(area_sqft / w))
    return {"length_in": w * 12, "width_in": d * 12}
