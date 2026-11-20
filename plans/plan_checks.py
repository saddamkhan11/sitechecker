"""Checks on a plan (one room or a whole single-storey house), using values from the Rules table.

Pure functions: pass rule values in, get a list of findings out.
Each finding: {"level": "ok"|"warn"|"error", "rule_id", "en", "roman", "ur", "room"}.
"""
from . import geometry as g

WALL_NAME = {"N": "top (north)", "S": "bottom (south)", "E": "right (east)", "W": "left (west)"}

DEFAULTS = {
    "PLAN-01": 80, "PLAN-02": 24, "PLAN-03": 10, "PLAN-04": 7, "PLAN-05": 50, "PLAN-06": 30, "PLAN-07": 18,
    "PLAN-08": 1.5, "PLAN-09": 36, "PLAN-10": 24,
    "PLAN-MIN-BEDROOM": 80, "PLAN-MIN-LIVING": 100, "PLAN-MIN-KITCHEN": 40, "PLAN-MIN-WASHROOM": 20, "PLAN-MIN-STORE": 16,
    "PLAN-SIDE-BEDROOM": 8, "PLAN-SIDE-LIVING": 9, "PLAN-SIDE-KITCHEN": 5, "PLAN-SIDE-WASHROOM": 4, "PLAN-SIDE-STORE": 4,
    "SCOPE-01": 14, "SCOPE-02": 20, "SCOPE-11": 1500, "SCOPE-12": 8,
}
MIN_AREA = {"room": "PLAN-01", "bedroom": "PLAN-MIN-BEDROOM", "living": "PLAN-MIN-LIVING", "kitchen": "PLAN-MIN-KITCHEN",
            "washroom": "PLAN-MIN-WASHROOM", "store": "PLAN-MIN-STORE"}
MIN_SIDE = {"room": "PLAN-04", "bedroom": "PLAN-SIDE-BEDROOM", "living": "PLAN-SIDE-LIVING", "kitchen": "PLAN-SIDE-KITCHEN",
            "washroom": "PLAN-SIDE-WASHROOM", "store": "PLAN-SIDE-STORE"}
NEEDS_LIGHT = {"room", "bedroom", "living", "kitchen"}  # 10% window rule
SMALL_DOOR_OK = {"washroom", "store"}  # PLAN-10 instead of PLAN-06


def _f(level, rule_id, en, roman, ur, room=None):
    return {"level": level, "rule_id": rule_id, "en": en, "roman": roman, "ur": ur, "room": room}


def check_plan(plan: dict, rules: dict | None = None) -> list:
    r = {**DEFAULTS, **{k: v for k, v in (rules or {}).items() if v is not None}}
    p = g.normalize(plan)
    out = []
    rooms = g.room_map(p)

    # ---- whole building ----
    area_in, _, box = g.footprint(p)
    covered = area_in / 144
    if covered > r["SCOPE-11"]:
        out.append(_f("error", "SCOPE-11", f"Covered area {covered:.0f} sq ft is over {r['SCOPE-11']:g} sq ft. This needs an engineer.",
                      f"Covered area {covered:.0f} sq ft hai, had {r['SCOPE-11']:g}. Engineer zaroori hai.",
                      f"تعمیر شدہ رقبہ {covered:.0f} مربع فٹ ہے، حد {r['SCOPE-11']:g}۔ انجینئر ضروری ہے۔"))
    if len(p["rooms"]) > r["SCOPE-12"]:
        out.append(_f("error", "SCOPE-12", f"{len(p['rooms'])} rooms is more than {r['SCOPE-12']:g}. This needs an engineer.",
                      f"{len(p['rooms'])} kamre, had {r['SCOPE-12']:g}. Engineer zaroori hai.",
                      f"{len(p['rooms'])} کمرے، حد {r['SCOPE-12']:g}۔ انجینئر ضروری ہے۔"))
    plot = p.get("plot")
    if plot:
        if box[0] < -0.5 or box[1] < -0.5 or box[2] > plot["length_in"] + 0.5 or box[3] > plot["width_in"] + 0.5:
            out.append(_f("error", "PLOT-01", "The building goes outside the plot.", "Building plot se bahar ja rahi hai.",
                          "عمارت پلاٹ سے باہر جا رہی ہے۔"))
    for a, b in g.overlaps(p):
        out.append(_f("error", "PLAN-09", f"{rooms[a]['name']} and {rooms[b]['name']} overlap or have less than one wall between them.",
                      f"{rooms[a]['name']} aur {rooms[b]['name']} ek doosre mein ghus rahe hain.",
                      f"{rooms[a]['name']} اور {rooms[b]['name']} ایک دوسرے میں گھس رہے ہیں۔", a))
    for a, b, gap in g.odd_gaps(p, r["PLAN-09"]):
        out.append(_f("warn", "PLAN-09", f"{gap:.0f} in gap between {rooms[a]['name']} and {rooms[b]['name']}: join them with one wall or leave at least {r['PLAN-09']:g} in.",
                      f"{rooms[a]['name']} aur {rooms[b]['name']} ke beech {gap:.0f} inch ka khali hissa: ek deewar se jorein ya {r['PLAN-09']:g} inch rasta chhorein.",
                      f"{rooms[a]['name']} اور {rooms[b]['name']} کے بیچ {gap:.0f} انچ خالی: ایک دیوار سے جوڑیں یا {r['PLAN-09']:g} انچ راستہ چھوڑیں۔", a))

    # ---- each room ----
    for room in p["rooms"]:
        nm, rid, typ = room["name"], room["id"], room.get("type", "room")
        L, W = room["length_in"] / 12, room["width_in"] / 12
        short, long_ = sorted([L, W])
        area = L * W
        if short > r["SCOPE-01"]:
            out.append(_f("error", "SCOPE-01", f"{nm}: short side {short:.1f} ft is over {r['SCOPE-01']:g} ft. This slab needs an engineer.",
                          f"{nm}: chhoti side {short:.1f} ft, had {r['SCOPE-01']:g} ft. Engineer zaroori hai.",
                          f"{nm}: چھوٹی سائیڈ {short:.1f} فٹ، حد {r['SCOPE-01']:g} فٹ۔ انجینئر ضروری ہے۔", rid))
        if long_ > r["SCOPE-02"]:
            out.append(_f("error", "SCOPE-02", f"{nm}: long side {long_:.1f} ft is over {r['SCOPE-02']:g} ft. This needs an engineer.",
                          f"{nm}: lambi side {long_:.1f} ft, had {r['SCOPE-02']:g} ft. Engineer zaroori hai.",
                          f"{nm}: لمبی سائیڈ {long_:.1f} فٹ، حد {r['SCOPE-02']:g} فٹ۔ انجینئر ضروری ہے۔", rid))
        ka, ks = MIN_AREA.get(typ, "PLAN-01"), MIN_SIDE.get(typ, "PLAN-04")
        if area < r[ka]:
            out.append(_f("warn", ka, f"{nm}: {area:.0f} sq ft is below {r[ka]:g} sq ft.",
                          f"{nm}: raqba {area:.0f} sq ft, kam az kam {r[ka]:g} ho.",
                          f"{nm}: رقبہ {area:.0f} مربع فٹ، کم از کم {r[ka]:g} ہو۔", rid))
        if short < r[ks]:
            out.append(_f("warn", ks, f"{nm}: short side {short:.1f} ft is below {r[ks]:g} ft.",
                          f"{nm}: chhoti side {short:.1f} ft, kam az kam {r[ks]:g} ft.",
                          f"{nm}: چھوٹی سائیڈ {short:.1f} فٹ، کم از کم {r[ks]:g} فٹ۔", rid))

        mine = [o for o in p["openings"] if o.get("room") == rid]
        doors = [o for o in mine if o["type"] == "door"]
        # a door in a neighbour's wall that leads into this room also counts
        doors_in = [o for o in p["openings"] if o["type"] == "door" and o.get("room") in rooms and o.get("room") != rid
                    and g.opening_target(p, rooms[o["room"]], o) == rid]
        if not doors and not doors_in:
            out.append(_f("error", "PLAN-06", f"{nm} has no door.", f"{nm} mein darwaza nahi.", f"{nm} میں دروازہ نہیں۔", rid))
        corner = r["PLAN-02"]
        by_wall = {}
        for o in mine:
            wall = o.get("wall")
            if wall not in g.WALLS:
                continue
            wl = g.wall_length(room, wall)
            off, w, oid = float(o["offset_in"]), float(o["width_in"]), o.get("id", "?")
            lab = ("Door", "Darwaza", "دروازہ") if o["type"] == "door" else ("Window", "Khirki", "کھڑکی")
            by_wall.setdefault(wall, []).append(o)
            if off < -0.5 or off + w > wl + 0.5:
                out.append(_f("error", "PLAN-02", f"{nm}: {lab[0]} {oid} goes past the end of the {WALL_NAME[wall]} wall.",
                              f"{nm}: {lab[1]} {oid} deewar se bahar hai.", f"{nm}: {lab[2]} {oid} دیوار سے باہر ہے۔", rid))
                continue
            if wl >= w + 2 * corner and (off < corner or wl - (off + w) < corner):
                gap = min(off, wl - off - w)
                out.append(_f("warn", "PLAN-02", f"{nm}: {lab[0]} {oid} is {gap:.0f} in from a corner; keep {corner:g} in.",
                              f"{nm}: {lab[1]} {oid} kone se {gap:.0f} inch par; {corner:g} inch rakhein.",
                              f"{nm}: {lab[2]} {oid} کونے سے {gap:.0f} انچ پر؛ {corner:g} انچ رکھیں۔", rid))
            target = g.opening_target(p, room, o)
            if o["type"] == "window" and target != "outside":
                out.append(_f("warn", "PLAN-03", f"{nm}: window {oid} is on an inside wall and gives no fresh air.",
                              f"{nm}: khirki {oid} andar ki deewar par hai, hawa nahi aayegi.",
                              f"{nm}: کھڑکی {oid} اندر کی دیوار پر ہے، ہوا نہیں آئے گی۔", rid))
            if o["type"] == "door":
                if target is None:
                    out.append(_f("warn", "PLAN-09", f"{nm}: door {oid} opens onto a gap, not a room or the outside.",
                                  f"{nm}: darwaza {oid} kisi kamre ya bahar nahi khulta.",
                                  f"{nm}: دروازہ {oid} کسی کمرے یا باہر نہیں کھلتا۔", rid))
                need = r["PLAN-10"] if typ in SMALL_DOOR_OK else r["PLAN-06"]
                rid_rule = "PLAN-10" if typ in SMALL_DOOR_OK else "PLAN-06"
                if w < need:
                    out.append(_f("warn", rid_rule, f"{nm}: door {oid} is {w:.0f} in wide; at least {need:g} in.",
                                  f"{nm}: darwaza {oid} {w:.0f} inch; kam az kam {need:g} inch.",
                                  f"{nm}: دروازہ {oid} {w:.0f} انچ؛ کم از کم {need:g} انچ۔", rid))
        for wall, items in by_wall.items():
            wl = g.wall_length(room, wall)
            total = sum(float(o["width_in"]) for o in items)
            if wl and total / wl * 100 > r["PLAN-05"] and wl > 60:
                out.append(_f("warn", "PLAN-05", f"{nm}: openings take {total / wl * 100:.0f}% of the {WALL_NAME[wall]} wall; keep under {r['PLAN-05']:g}%.",
                              f"{nm}: is deewar ka {total / wl * 100:.0f}% khula; {r['PLAN-05']:g}% se kam.",
                              f"{nm}: اس دیوار کا {total / wl * 100:.0f}% کھلا؛ {r['PLAN-05']:g}% سے کم۔", rid))
            items = sorted(items, key=lambda o: float(o["offset_in"]))
            for a, b in zip(items, items[1:]):
                gap = float(b["offset_in"]) - (float(a["offset_in"]) + float(a["width_in"]))
                if gap < 0:
                    out.append(_f("error", "PLAN-07", f"{nm}: {a['id']} and {b['id']} overlap.", f"{nm}: {a['id']} aur {b['id']} ek doosre par.",
                                  f"{nm}: {a['id']} اور {b['id']} ایک دوسرے پر۔", rid))
                elif gap < r["PLAN-07"]:
                    out.append(_f("warn", "PLAN-07", f"{nm}: only {gap:.0f} in of wall between {a['id']} and {b['id']}; keep {r['PLAN-07']:g} in.",
                                  f"{nm}: {a['id']} aur {b['id']} ke beech sirf {gap:.0f} inch; {r['PLAN-07']:g} inch rakhein.",
                                  f"{nm}: {a['id']} اور {b['id']} کے بیچ صرف {gap:.0f} انچ؛ {r['PLAN-07']:g} انچ رکھیں۔", rid))

        win = sum(float(o["width_in"]) * float(o["height_in"]) for o in mine
                  if o["type"] == "window" and g.opening_target(p, room, o) == "outside") / 144
        if typ in NEEDS_LIGHT:
            need = area * r["PLAN-03"] / 100
            if win < need:
                out.append(_f("warn", "PLAN-03", f"{nm}: window area {win:.1f} sq ft is below {need:.1f} sq ft ({r['PLAN-03']:g}% of floor).",
                              f"{nm}: khirkiyon ka raqba {win:.1f} sq ft, kam az kam {need:.1f} chahiye.",
                              f"{nm}: کھڑکیوں کا رقبہ {win:.1f} مربع فٹ، کم از کم {need:.1f} چاہیے۔", rid))
        if typ == "washroom" and win < r["PLAN-08"]:
            out.append(_f("warn", "PLAN-08", f"{nm}: needs a ventilator of at least {r['PLAN-08']:g} sq ft on an outside wall (or an exhaust fan).",
                          f"{nm}: bahar ki deewar par kam az kam {r['PLAN-08']:g} sq ft ka roshandan (ya exhaust fan) chahiye.",
                          f"{nm}: باہر کی دیوار پر کم از کم {r['PLAN-08']:g} مربع فٹ کا روشن دان (یا ایگزاسٹ فین) چاہیے۔", rid))

    if not out:
        out.append(_f("ok", "", "No problem found by the plan checks.", "Plan checks mein koi masla nazar nahi aaya.",
                      "نقشے کی جانچ میں کوئی مسئلہ نظر نہیں آیا۔"))
    return out


def has_scope_error(findings):
    return [f for f in findings if f["level"] == "error" and f["rule_id"].startswith("SCOPE")]


def clean_plan(raw: dict) -> dict:
    """Keep only known fields, as numbers, so a bad request can not store junk. Returns format 2."""
    def num(v, lo, hi):
        v = float(v)
        if not lo <= v <= hi:
            raise ValueError(f"{v} is outside {lo}-{hi}")
        return round(v, 1)

    p = g.normalize(raw)
    out = {"format": 2, "wall_in": num(p.get("wall_in", 9), 4, 18), "plot": None, "rooms": [], "openings": []}
    if p.get("plot"):
        out["plot"] = {"length_in": num(p["plot"]["length_in"], 60, 2400), "width_in": num(p["plot"]["width_in"], 60, 2400)}
    ids = set()
    for i, r in enumerate(p["rooms"][:12]):
        rid = str(r.get("id") or f"r{i + 1}")[:8]
        if rid in ids:
            rid = f"r{i + 1}x"
        ids.add(rid)
        typ = r.get("type") if r.get("type") in g.ROOM_TYPES else "room"
        out["rooms"].append({
            "id": rid, "name": str(r.get("name") or g.ROOM_TYPES[typ][0])[:30], "type": typ,
            "x_in": num(r.get("x_in", 9), -100, 2400), "y_in": num(r.get("y_in", 9), -100, 2400),
            "length_in": num(r["length_in"], 24, 600), "width_in": num(r["width_in"], 24, 600),
        })
    if not out["rooms"]:
        raise ValueError("At least one room is needed")
    for i, o in enumerate(p.get("openings", [])[:40]):
        kind = "door" if o.get("type") == "door" else "window"
        room = o.get("room") if o.get("room") in ids else out["rooms"][0]["id"]
        item = {
            "id": str(o.get("id") or f"{kind[0]}{i + 1}")[:8], "room": room, "type": kind,
            "wall": o.get("wall") if o.get("wall") in g.WALLS else "S",
            "offset_in": num(o.get("offset_in", 0), -100, 600),
            "width_in": num(o.get("width_in", 36), 6, 240),
            "height_in": num(o.get("height_in", 84 if kind == "door" else 48), 6, 110),
        }
        if kind == "window":
            item["sill_in"] = num(o.get("sill_in", 36), 0, 90)
        out["openings"].append(item)
    return out
