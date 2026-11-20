"""Geometry for single-storey plans with one or many rooms. Pure Python, all sizes in inches.

Plan format 2:
    {"format": 2, "wall_in": 9,
     "plot": {"length_in": 360, "width_in": 720} | None,
     "rooms": [{"id": "r1", "name": "Bedroom", "type": "bedroom",
                "x_in": 9, "y_in": 9, "length_in": 144, "width_in": 120}],
     "openings": [{"id": "d1", "room": "r1", "type": "door", "wall": "S",
                   "offset_in": 30, "width_in": 36, "height_in": 84}]}

x/y is the inside top-left corner of the room. "length" runs along x, "width" along y.
Two rooms share a wall when the gap between their inside faces equals the wall thickness.
Format 1 (one room, no "rooms" key) is converted on the fly by normalize().
"""
from __future__ import annotations

import copy

ROOM_TYPES = {
    # type: (English, Roman Urdu, Urdu, default length ft, default width ft)
    "room": ("Room", "Kamra", "کمرہ", 12, 12),
    "bedroom": ("Bedroom", "Bedroom", "بیڈروم", 12, 12),
    "living": ("Living room", "Drawing / lounge", "لاؤنج", 14, 12),
    "kitchen": ("Kitchen", "Kitchen / bawarchi khana", "کچن", 10, 8),
    "washroom": ("Washroom", "Washroom / ghusl khana", "واش روم", 7, 5),
    "store": ("Store", "Store", "سٹور", 6, 6),
}
WET_TYPES = {"washroom", "kitchen"}
WALLS = ("N", "S", "E", "W")
TOL = 0.75  # inches: a gap within wall +/- TOL counts as a shared wall


def normalize(plan: dict) -> dict:
    """Return a format-2 copy of any plan."""
    p = copy.deepcopy(plan or {})
    if p.get("format") == 2 and "rooms" in p:
        p.setdefault("plot", None)
        p.setdefault("openings", [])
        return p
    t = float(p.get("wall_in", 9))
    room = {"id": "r1", "name": "Room", "type": "room", "x_in": t, "y_in": t,
            "length_in": float(p["length_in"]), "width_in": float(p["width_in"])}
    ops = [{**o, "room": "r1"} for o in p.get("openings", [])]
    return {"format": 2, "wall_in": t, "plot": None, "rooms": [room], "openings": ops}


def room_map(plan):
    return {r["id"]: r for r in plan["rooms"]}


def wall_length(room, wall):
    return float(room["length_in"] if wall in ("N", "S") else room["width_in"])


def area_sqft(room):
    return float(room["length_in"]) * float(room["width_in"]) / 144


# ---------- wall centre lines ----------
def _room_edges(room, t):
    """The four centre-line edges of a room's walls: ('h'|'v', fixed coord, start, end)."""
    x0, y0 = room["x_in"] - t / 2, room["y_in"] - t / 2
    x1, y1 = room["x_in"] + room["length_in"] + t / 2, room["y_in"] + room["width_in"] + t / 2
    return [("h", y0, x0, x1), ("h", y1, x0, x1), ("v", x0, y0, y1), ("v", x1, y0, y1)]


def _key(v):
    return round(v * 2) / 2  # snap to half inch so shared walls line up


def wall_segments(plan):
    """Centre-line wall segments with how many rooms use each: [(kind, fixed, a, b, count)]."""
    t = float(plan["wall_in"])
    lines = {}
    for r in plan["rooms"]:
        for kind, fixed, a, b in _room_edges(r, t):
            lines.setdefault((kind, _key(fixed)), []).append((a, b))
    out = []
    for (kind, fixed), spans in lines.items():
        cuts = sorted({_key(v) for s in spans for v in s})
        for a, b in zip(cuts, cuts[1:]):
            if b - a < 0.25:
                continue
            mid = (a + b) / 2
            n = sum(1 for s in spans if s[0] - 0.01 <= mid <= s[1] + 0.01)
            if n:
                out.append((kind, fixed, a, b, n))
    return out


def centre_line_length(plan):
    return sum(b - a for _, _, a, b, _ in wall_segments(plan))


def exterior_centre_line(plan):
    return sum(b - a for _, _, a, b, n in wall_segments(plan) if n == 1)


# ---------- footprint (union of outer rectangles) ----------
def _outer_rects(plan):
    t = float(plan["wall_in"])
    return [(r["x_in"] - t, r["y_in"] - t, r["x_in"] + r["length_in"] + t, r["y_in"] + r["width_in"] + t)
            for r in plan["rooms"]]


def _grid(rects):
    xs = sorted({_key(v) for r in rects for v in (r[0], r[2])})
    ys = sorted({_key(v) for r in rects for v in (r[1], r[3])})
    filled = [[any(r[0] - 0.01 <= (xs[i] + xs[i + 1]) / 2 <= r[2] + 0.01 and r[1] - 0.01 <= (ys[j] + ys[j + 1]) / 2 <= r[3] + 0.01
                   for r in rects) for j in range(len(ys) - 1)] for i in range(len(xs) - 1)]
    return xs, ys, filled


def footprint(plan):
    """(area sq in, perimeter in, bounding box) of the building's outer outline."""
    rects = _outer_rects(plan)
    if not rects:
        return 0.0, 0.0, (0, 0, 0, 0)
    xs, ys, f = _grid(rects)
    nx, ny = len(xs) - 1, len(ys) - 1
    area = perim = 0.0
    for i in range(nx):
        for j in range(ny):
            if not f[i][j]:
                continue
            w, h = xs[i + 1] - xs[i], ys[j + 1] - ys[j]
            area += w * h
            if i == 0 or not f[i - 1][j]:
                perim += h
            if i == nx - 1 or not f[i + 1][j]:
                perim += h
            if j == 0 or not f[i][j - 1]:
                perim += w
            if j == ny - 1 or not f[i][j + 1]:
                perim += w
    box = (min(r[0] for r in rects), min(r[1] for r in rects), max(r[2] for r in rects), max(r[3] for r in rects))
    return area, perim, box


# ---------- relations between rooms ----------
def neighbour_across(plan, room, wall, a=None, b=None):
    """The room on the other side of `wall` of `room` (sharing it over [a, b] along the wall), or None."""
    t = float(plan["wall_in"])
    a = 0 if a is None else a
    b = wall_length(room, wall) if b is None else b
    rx, ry = room["x_in"], room["y_in"]
    for other in plan["rooms"]:
        if other is room or other["id"] == room["id"]:
            continue
        ox, oy = other["x_in"], other["y_in"]
        if wall in ("N", "S"):
            if wall == "N":
                gap = ry - (oy + other["width_in"])
            else:
                gap = oy - (ry + room["width_in"])
            lo, hi = rx + a, rx + b
            if abs(gap - t) <= TOL and ox <= lo + 0.5 and ox + other["length_in"] >= hi - 0.5:
                return other
        else:
            if wall == "W":
                gap = rx - (ox + other["length_in"])
            else:
                gap = ox - (rx + room["length_in"])
            lo, hi = ry + a, ry + b
            if abs(gap - t) <= TOL and oy <= lo + 0.5 and oy + other["width_in"] >= hi - 0.5:
                return other
    return None


def free_ranges(plan, room, wall, block_gap=36):
    """Parts [a, b] of a wall (measured along it) with no other room behind it: outside wall faces.
    A neighbour closer than wall + block_gap blocks the wall (no light or door there)."""
    t = float(plan["wall_in"])
    L = wall_length(room, wall)
    free = [(0.0, L)]
    rx, ry = room["x_in"], room["y_in"]
    for other in plan["rooms"]:
        if other["id"] == room["id"]:
            continue
        ox, oy = other["x_in"], other["y_in"]
        if wall == "N":
            gap, lo, hi = ry - (oy + other["width_in"]), ox - rx, ox + other["length_in"] - rx
        elif wall == "S":
            gap, lo, hi = oy - (ry + room["width_in"]), ox - rx, ox + other["length_in"] - rx
        elif wall == "W":
            gap, lo, hi = rx - (ox + other["length_in"]), oy - ry, oy + other["width_in"] - ry
        else:
            gap, lo, hi = ox - (rx + room["length_in"]), oy - ry, oy + other["width_in"] - ry
        if gap < -TOL or gap >= t + block_gap:
            continue
        lo, hi = lo - t, hi + t  # the neighbour's own walls block too
        nxt = []
        for a, b in free:
            if hi <= a or lo >= b:
                nxt.append((a, b))
                continue
            if lo > a:
                nxt.append((a, lo))
            if hi < b:
                nxt.append((hi, b))
        free = [(a, b) for a, b in nxt if b - a > 1]
    return free


def overlaps(plan):
    """Pairs of rooms whose walls collide (inside faces closer than one wall thickness)."""
    t = float(plan["wall_in"]) - TOL
    rooms, out = plan["rooms"], []
    for i, a in enumerate(rooms):
        for b in rooms[i + 1:]:
            sep_x = max(b["x_in"] - (a["x_in"] + a["length_in"]), a["x_in"] - (b["x_in"] + b["length_in"]))
            sep_y = max(b["y_in"] - (a["y_in"] + a["width_in"]), a["y_in"] - (b["y_in"] + b["width_in"]))
            if sep_x < t and sep_y < t:
                out.append((a["id"], b["id"]))
    return out


def odd_gaps(plan, min_passage):
    """Rooms side by side with a gap that is neither a shared wall nor a usable passage."""
    t = float(plan["wall_in"])
    rooms, out = plan["rooms"], []
    for i, a in enumerate(rooms):
        for b in rooms[i + 1:]:
            for lo_a, len_a, lo_b, len_b, plo_a, plen_a, plo_b, plen_b in (
                (a["x_in"], a["length_in"], b["x_in"], b["length_in"], a["y_in"], a["width_in"], b["y_in"], b["width_in"]),
                (a["y_in"], a["width_in"], b["y_in"], b["width_in"], a["x_in"], a["length_in"], b["x_in"], b["length_in"]),
            ):
                gap = max(lo_b - (lo_a + len_a), lo_a - (lo_b + len_b))
                overlap = min(plo_a + plen_a, plo_b + plen_b) - max(plo_a, plo_b)
                if overlap > 12 and t + TOL < gap < t + min_passage:
                    out.append((a["id"], b["id"], gap - t))
    return out


def opening_exterior(plan, room, o):
    a, b = o["offset_in"], o["offset_in"] + o["width_in"]
    return any(fa - 0.5 <= a and b <= fb + 0.5 for fa, fb in free_ranges(plan, room, o["wall"], block_gap=0))


def opening_target(plan, room, o):
    """'outside', a room id the door leads into, or None when it opens onto a blocked gap."""
    if opening_exterior(plan, room, o):
        return "outside"
    other = neighbour_across(plan, room, o["wall"], o["offset_in"], o["offset_in"] + o["width_in"])
    return other["id"] if other else None


def summary(plan):
    p = normalize(plan)
    area, _, box = footprint(p)
    return {
        "rooms": [{"id": r["id"], "name": r["name"], "type": r["type"],
                   "size_ft": f"{r['length_in'] / 12:g} x {r['width_in'] / 12:g}", "area_sqft": round(area_sqft(r))}
                  for r in p["rooms"]],
        "covered_area_sqft": round(area / 144),
        "outer_size_ft": f"{(box[2] - box[0]) / 12:.1f} x {(box[3] - box[1]) / 12:.1f}",
        "plot_ft": (f"{p['plot']['length_in'] / 12:g} x {p['plot']['width_in'] / 12:g}" if p.get("plot") else None),
        "openings": [{"id": o["id"], "room": o.get("room"), "type": o["type"], "wall": o["wall"],
                      "width_ft": round(o["width_in"] / 12, 2)} for o in p["openings"]],
    }
