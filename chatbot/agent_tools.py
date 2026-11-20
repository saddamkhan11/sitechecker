"""Tools the agent can call. Each tool runs OUR Python code and validates what it writes.

The model only decides WHICH tool to call with WHAT arguments; numbers, rule checks,
layouts and quantities all come from code and the Rules table.
"""
import datetime as dt
from decimal import Decimal, InvalidOperation

from django.urls import reverse
from django.utils import timezone

from plans import geometry
from plans.layout import auto_layout, place_opening, plot_from_area, relayout, room_spec
from plans.models import Plan
from plans.plan_checks import check_plan
from plans.service import PlanRefused, save_plan
from projects.models import ChecklistItem, ProjectStage, Rate, rule_value, rule_values
from projects.scope import check_room
from projects.stages import STAGE_CODES

from .tools import calculate_materials, lookup_rule

ROOM_TYPE_ENUM = list(geometry.ROOM_TYPES)
MATERIALS = ["brick", "cement", "sand", "crush", "steel"]


def _fn(name, description, properties=None, required=None):
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties or {}, "required": required or []},
    }}


ROOM_ITEM = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "type": {"type": "string", "enum": ROOM_TYPE_ENUM},
        "length_ft": {"type": "number"},
        "width_ft": {"type": "number"},
        "count": {"type": "integer"},
    },
    "required": ["type"],
}
PLOT_PROPS = {
    "plot_length_ft": {"type": "number", "description": "front"},
    "plot_width_ft": {"type": "number", "description": "depth"},
    "plot_marla": {"type": "number"},
    "plot_sq_yards": {"type": "number", "description": "gaz"},
}

TOOLS = [
    _fn("lookup_rule", "Rules by ID (FND-01) or English keywords.",
        {"query": {"type": "string"}}, ["query"]),
    _fn("get_project", "Facts, rooms with ids, doors/windows with ids."),
    _fn("update_project", "Save details the user gave (only those fields).", {
        "name": {"type": "string"},
        "project_type": {"type": "string", "enum": ["room", "washroom", "kitchen", "house"]},
        "city": {"type": "string"},
        **PLOT_PROPS,
        "budget_pkr": {"type": "number"},
        "start_date": {"type": "string", "description": "YYYY-MM-DD"},
        "wall_type": {"type": "string"},
        "roof_type": {"type": "string"},
    }),
    _fn("design_layout", "Design the whole layout from a room list, fitted in the plot (doors and windows placed).",
        {"rooms": {"type": "array", "items": ROOM_ITEM}, **PLOT_PROPS}, ["rooms"]),
    _fn("add_room", "Add a room and re-arrange.", {
        "name": {"type": "string"}, "type": {"type": "string", "enum": ROOM_TYPE_ENUM},
        "length_ft": {"type": "number"}, "width_ft": {"type": "number"}}, ["type"]),
    _fn("edit_room", "Rename/retype/resize a room by id, re-arrange.", {
        "room_id": {"type": "string"}, "name": {"type": "string"}, "type": {"type": "string", "enum": ROOM_TYPE_ENUM},
        "length_ft": {"type": "number"}, "width_ft": {"type": "number"}}, ["room_id"]),
    _fn("remove_room", "Remove a room by id, re-arrange.", {"room_id": {"type": "string"}}, ["room_id"]),
    _fn("add_opening", "Add a door/window; wall and offset optional (best spot).", {
        "room_id": {"type": "string"}, "type": {"type": "string", "enum": ["door", "window"]},
        "wall": {"type": "string", "enum": ["N", "S", "E", "W"], "description": "S=front"},
        "width_ft": {"type": "number"}, "height_ft": {"type": "number"}, "offset_ft": {"type": "number"}}, ["room_id", "type"]),
    _fn("move_opening", "Move/resize a door or window by id.", {
        "opening_id": {"type": "string"}, "wall": {"type": "string", "enum": ["N", "S", "E", "W"]},
        "offset_ft": {"type": "number"}, "width_ft": {"type": "number"}}, ["opening_id"]),
    _fn("remove_opening", "Remove a door or window by id.", {"opening_id": {"type": "string"}}, ["opening_id"]),
    _fn("check_plan", "Rule problems in the current plan."),
    _fn("calculate_materials", "Material quantities and cost."),
    _fn("save_rates", "Save prices the user gave.", {
        "brick_per_1000": {"type": "number"}, "cement_per_bag": {"type": "number"}, "sand_per_cft": {"type": "number"},
        "crush_per_cft": {"type": "number"}, "steel_per_kg": {"type": "number"}}),
    _fn("compare_mistri_demand", "Mistri demand vs estimate, in %.", {
        m: {"type": "number"} for m in MATERIALS}),
    _fn("get_stage_checklist", "Checklist of a stage with latest results.", {
        "stage": {"type": "string", "enum": STAGE_CODES}}),
    _fn("set_stage_status", "Mark a stage started/done.", {
        "stage": {"type": "string", "enum": STAGE_CODES},
        "status": {"type": "string", "enum": ["not_started", "in_progress", "done"]}}, ["stage", "status"]),
    _fn("add_diary_entry", "Diary entry: material received, payment or note.", {
        "kind": {"type": "string", "enum": ["material", "payment", "note"]},
        "date": {"type": "string", "description": "YYYY-MM-DD"},
        "material": {"type": "string", "enum": MATERIALS + ["other"]}, "quantity": {"type": "number"},
        "payment_type": {"type": "string", "enum": ["labour", "material", "transport", "other"]},
        "amount": {"type": "number"}, "paid_to": {"type": "string"}, "note": {"type": "string"}}, ["kind"]),
    _fn("get_diary_totals", "Material received vs estimate, payments."),
    _fn("finish_setup", "Finish setup (needs city and a layout)."),
    _fn("setup_project", "One call that saves the details, designs the layout and finishes setup.", {
        "city": {"type": "string"}, "project_type": {"type": "string", "enum": ["room", "washroom", "kitchen", "house"]},
        "rooms": {"type": "array", "items": ROOM_ITEM}, **PLOT_PROPS,
        "budget_pkr": {"type": "number"}, "start_date": {"type": "string", "description": "YYYY-MM-DD"}}, ["city", "rooms"]),
]

# While setting up, the agent only needs these (fewer tokens per call: Groq limits tokens per minute).
SETUP_TOOLS = {"lookup_rule", "get_project", "update_project", "setup_project", "design_layout", "finish_setup",
               "calculate_materials"}


def tools_for(project):
    if project.onboarded:
        return [t for t in TOOLS if t["function"]["name"] != "setup_project"]
    return [t for t in TOOLS if t["function"]["name"] in SETUP_TOOLS]


def _ui(label, url):
    return {"label": label, "url": url}


def _dec(v):
    try:
        d = Decimal(str(v))
        return d if d >= 0 else None
    except (InvalidOperation, TypeError):
        return None


def _plot_from_args(project, a):
    if a.get("plot_length_ft") and a.get("plot_width_ft"):
        return {"length_in": float(a["plot_length_ft"]) * 12, "width_in": float(a["plot_width_ft"]) * 12}
    if a.get("plot_marla"):
        return plot_from_area(float(a["plot_marla"]) * rule_value("PLOT-MARLA", 225))
    if a.get("plot_sq_yards"):
        return plot_from_area(float(a["plot_sq_yards"]) * 9)
    if project.plot_length_ft and project.plot_width_ft:
        return {"length_in": float(project.plot_length_ft) * 12, "width_in": float(project.plot_width_ft) * 12}
    return None


def _warnings(findings):
    return [{"level": f["level"], "rule_id": f["rule_id"], "problem": f["en"]} for f in findings if f["level"] != "ok"]


def _current(project):
    plan = Plan.latest_for(project)
    return geometry.normalize(plan.data) if plan else None


def _save(project, data, what):
    try:
        plan, findings = save_plan(project, data)
    except PlanRefused as e:
        return {"ok": False, "needs_engineer": bool(e.findings), "error": str(e), "problems": _warnings(e.findings)}
    return {"ok": True, "done": what, "plan_version": plan.version, "plan": geometry.summary(plan.data),
            "problems": _warnings(findings), "ui": _ui("📐 Naqsha / Plan", reverse("plan_editor", args=[project.pk]))}


class Tools:
    """Tool handlers bound to one project."""

    def __init__(self, project):
        self.p = project

    # ---------- reading ----------
    def lookup_rule(self, a):
        return {"rules": lookup_rule(a.get("query", ""))}

    def get_project(self, a):
        self.p.refresh_from_db()
        plan = _current(self.p)
        return {"facts": self.p.facts(),
                "rooms": [{k: r[k] for k in ("id", "name", "type")} | {"size_ft": f"{r['length_in'] / 12:g} x {r['width_in'] / 12:g}"}
                          for r in (plan["rooms"] if plan else [])],
                "openings": [{k: o.get(k) for k in ("id", "room", "type", "wall")} | {"width_ft": o["width_in"] / 12, "offset_ft": o["offset_in"] / 12}
                             for o in (plan["openings"] if plan else [])]}

    def check_plan(self, a):
        plan = _current(self.p)
        if not plan:
            return {"error": "No plan yet. Call design_layout first."}
        return {"problems": _warnings(check_plan(plan, rule_values())) or "none",
                "ui": _ui("📐 Naqsha / Plan", reverse("plan_editor", args=[self.p.pk]))}

    def calculate_materials(self, a):
        full = calculate_materials(self.p)
        if "materials" not in full:
            return full
        cost = full["cost_pkr"]
        return {"materials": full["materials"], "units": full["units"],
                "cost_rs": {"lines": cost["lines"], "total": cost["total"], "rates_missing": cost["missing"]},
                "by_section": full["by_section"], "ui": _ui("🧮 Material", reverse("materials", args=[self.p.pk]))}

    # ---------- project ----------
    def update_project(self, a):
        p, changed = self.p, []
        if a.get("wall_type") and a["wall_type"].lower() not in ("brick", "eent", "bricks"):
            return {"ok": False, "needs_engineer": True, "error": "Only brick walls are covered [SCOPE-03]. Other walls need an engineer."}
        if a.get("roof_type") and a["roof_type"].lower() not in ("rcc_slab", "rcc", "slab", "lanter"):
            return {"ok": False, "needs_engineer": True, "error": "Only an RCC slab roof is covered [SCOPE-03]. Other roofs need an engineer."}
        for f in ("name", "city"):
            if a.get(f):
                setattr(p, f, str(a[f]).strip()[:60].title() if f == "city" else str(a[f]).strip()[:100])
                changed.append(f)
        if a.get("project_type") in dict(p.TYPE_CHOICES):
            p.project_type = a["project_type"]
            changed.append("project_type")
        plot = None
        if any(a.get(k) for k in PLOT_PROPS):
            plot = _plot_from_args(p, a)
            p.plot_length_ft, p.plot_width_ft = round(plot["length_in"] / 12, 2), round(plot["width_in"] / 12, 2)
            changed.append("plot")
        if a.get("budget_pkr") is not None and _dec(a["budget_pkr"]) is not None:
            p.budget_pkr = int(_dec(a["budget_pkr"]))
            changed.append("budget")
        if a.get("start_date"):
            try:
                p.start_date = dt.date.fromisoformat(a["start_date"])
                changed.append("start_date")
            except ValueError:
                return {"ok": False, "error": "start_date must be YYYY-MM-DD"}
        p.wall_type, p.roof_type = "brick", "rcc_slab"
        p.save()
        return {"ok": True, "saved": changed, "facts": p.facts(),
                "plot_ft": f"{float(p.plot_length_ft):g} x {float(p.plot_width_ft):g}" if p.plot_length_ft else None}

    def finish_setup(self, a):
        p = self.p
        p.refresh_from_db()
        if not p.city:
            return {"ok": False, "error": "City is still missing. Ask the user."}
        if not Plan.latest_for(p):
            return {"ok": False, "error": "No layout yet. Call design_layout first."}
        p.wall_type, p.roof_type = p.wall_type or "brick", p.roof_type or "rcc_slab"
        p.onboarding_step = p.ONBOARDING_DONE
        p.in_scope = True
        if p.name in ("", "My room"):
            p.name = p.default_name()
        p.save()
        p.ensure_stages()
        p.refresh_current_stage()
        return {"ok": True, "stages": [s.stage for s in p.stages.all()], "first_stage": p.current_stage,
                "ui": _ui("🏠 Project", reverse("project_detail", args=[p.pk]))}

    def setup_project(self, a):
        """update_project + design_layout + finish_setup in one step."""
        details = {k: a[k] for k in ("city", "project_type", "budget_pkr", "start_date", *PLOT_PROPS) if a.get(k) is not None}
        if not details.get("project_type"):
            rooms = a.get("rooms") or []
            n = sum(max(1, int(r.get("count") or 1)) for r in rooms)
            details["project_type"] = ("house" if n > 1 else
                                       rooms[0].get("type") if rooms and rooms[0].get("type") in ("washroom", "kitchen") else "room")
        out = self.update_project(details)
        if not out.get("ok"):
            return out
        out = self.design_layout({"rooms": a.get("rooms") or [], **{k: a[k] for k in PLOT_PROPS if a.get(k)}})
        if not out.get("ok"):
            return out
        fin = self.finish_setup({})
        if not fin.get("ok"):
            return fin
        return {**out, "done": "project saved, layout designed and setup finished", "first_stage": fin["first_stage"],
                "ui": out["ui"]}

    # ---------- layout ----------
    def design_layout(self, a):
        specs = []
        for item in (a.get("rooms") or [])[:12]:
            for i in range(max(1, min(int(item.get("count") or 1), 8))):
                s = room_spec(item.get("name"), item.get("type", "room"), item.get("length_ft"), item.get("width_ft"))
                if int(item.get("count") or 1) > 1 and not item.get("name"):
                    s["name"] = f"{s['name']} {i + 1}"
                specs.append(s)
        if not specs:
            return {"ok": False, "error": "Give at least one room."}
        for s in specs:
            res = check_room(s["length_in"] / 12, s["width_in"] / 12)
            if not res.ok:
                return {"ok": False, "needs_engineer": True, "error": f"{s['name']}: {res.reason_en} [{res.rule_id}]"}
        plot = _plot_from_args(self.p, a)
        if plot:
            self.p.plot_length_ft, self.p.plot_width_ft = round(plot["length_in"] / 12, 2), round(plot["width_in"] / 12, 2)
            self.p.save(update_fields=["plot_length_ft", "plot_width_ft"])
        plan = auto_layout(specs, plot, rule_value("WALL-01", 9), rule_values())
        return _save(self.p, plan, f"designed {len(specs)} room(s)")

    def _relayout_with(self, change):
        plan = _current(self.p)
        if not plan:
            return {"ok": False, "error": "No plan yet. Call design_layout first."}
        err = change(plan)
        if err:
            return {"ok": False, "error": err}
        if not plan["rooms"]:
            return {"ok": False, "error": "A plan needs at least one room."}
        for r in plan["rooms"]:
            res = check_room(r["length_in"] / 12, r["width_in"] / 12)
            if not res.ok:
                return {"ok": False, "needs_engineer": True, "error": f"{r['name']}: {res.reason_en} [{res.rule_id}]"}
        out = _save(self.p, relayout(plan, rule_values()), "re-arranged the layout; doors and windows were placed again")
        return out

    def add_room(self, a):
        def change(plan):
            s = room_spec(a.get("name"), a.get("type", "room"), a.get("length_ft"), a.get("width_ft"))
            plan["rooms"].append({"id": f"r{len(plan['rooms']) + 1}", "x_in": 0, "y_in": 0, **s})
        return self._relayout_with(change)

    def edit_room(self, a):
        def change(plan):
            room = next((r for r in plan["rooms"] if r["id"] == a.get("room_id")), None)
            if not room:
                return f"No room {a.get('room_id')}. Use get_project to see room ids."
            if a.get("name"):
                room["name"] = str(a["name"])[:30]
            if a.get("type") in geometry.ROOM_TYPES:
                room["type"] = a["type"]
            L = float(a["length_ft"]) * 12 if a.get("length_ft") else room["length_in"]
            W = float(a["width_ft"]) * 12 if a.get("width_ft") else room["width_in"]
            room["length_in"], room["width_in"] = max(L, W), min(L, W)
        return self._relayout_with(change)

    def remove_room(self, a):
        def change(plan):
            before = len(plan["rooms"])
            plan["rooms"] = [r for r in plan["rooms"] if r["id"] != a.get("room_id")]
            if len(plan["rooms"]) == before:
                return f"No room {a.get('room_id')}."
        return self._relayout_with(change)

    # ---------- openings ----------
    def add_opening(self, a):
        plan = _current(self.p)
        if not plan:
            return {"ok": False, "error": "No plan yet."}
        room = next((r for r in plan["rooms"] if r["id"] == a.get("room_id")), None)
        if not room:
            return {"ok": False, "error": f"No room {a.get('room_id')}."}
        kind = "door" if a.get("type") == "door" else "window"
        width = float(a.get("width_ft") or (3 if kind == "door" else 4)) * 12
        height = float(a.get("height_ft") or (7 if kind == "door" else 4)) * 12
        walls = (a["wall"],) if a.get("wall") in geometry.WALLS else None
        if a.get("offset_ft") is not None and walls:
            oid = ("d" if kind == "door" else "w") + str(1 + sum(1 for o in plan["openings"] if o["type"] == kind))
            while any(o["id"] == oid for o in plan["openings"]):
                oid += "x"
            o = {"id": oid, "room": room["id"], "type": kind, "wall": walls[0], "offset_in": float(a["offset_ft"]) * 12,
                 "width_in": width, "height_in": height}
            if kind == "window":
                o["sill_in"] = 36
            plan["openings"].append(o)
        else:
            o = place_opening(plan, room, kind, width, height, walls=walls, outside_only=(kind == "window"))
            if not o:
                return {"ok": False, "error": "No free wall space for it in this room."}
        return _save(self.p, plan, f"added {kind} {o['id']} to {room['name']}")

    def move_opening(self, a):
        plan = _current(self.p)
        o = next((x for x in (plan or {}).get("openings", []) if x["id"] == a.get("opening_id")), None)
        if not o:
            return {"ok": False, "error": f"No opening {a.get('opening_id')}."}
        if a.get("wall") in geometry.WALLS:
            o["wall"] = a["wall"]
        if a.get("width_ft"):
            o["width_in"] = float(a["width_ft"]) * 12
        if a.get("offset_ft") is not None:
            o["offset_in"] = float(a["offset_ft"]) * 12
        return _save(self.p, plan, f"moved {o['id']}")

    def remove_opening(self, a):
        plan = _current(self.p)
        if not plan:
            return {"ok": False, "error": "No plan yet."}
        before = len(plan["openings"])
        plan["openings"] = [o for o in plan["openings"] if o["id"] != a.get("opening_id")]
        if len(plan["openings"]) == before:
            return {"ok": False, "error": f"No opening {a.get('opening_id')}."}
        return _save(self.p, plan, f"removed {a.get('opening_id')}")

    # ---------- money ----------
    def save_rates(self, a):
        keys = {"brick_per_1000": "brick", "cement_per_bag": "cement", "sand_per_cft": "sand",
                "crush_per_cft": "crush", "steel_per_kg": "steel"}
        if not self.p.city:
            return {"ok": False, "error": "Set the city first."}
        saved = {}
        for k, mat in keys.items():
            price = _dec(a.get(k)) if a.get(k) is not None else None
            if price:
                Rate.objects.create(material=mat, price=price, city=self.p.city, entered_by=self.p.owner)
                saved[mat] = float(price)
        return {"ok": bool(saved), "saved": saved, "city": self.p.city, "date": timezone.localdate().isoformat(),
                "ui": _ui("🧮 Material", reverse("materials", args=[self.p.pk]))}

    def compare_mistri_demand(self, a):
        from calculator import calc
        from calculator.service import build_estimate

        est = build_estimate(self.p)
        if est is None:
            return {"error": "No plan yet."}
        demand = {m: float(a[m]) for m in MATERIALS if a.get(m) is not None}
        est.mistri_demand = {**(est.mistri_demand or {}), **demand}
        est.save(update_fields=["mistri_demand"])
        tol = rule_value("CALC-MISTRI-TOLERANCE", 10)
        return {"tolerance_pct": tol, "comparison": calc.compare_demand(est.materials, est.mistri_demand, tol),
                "ui": _ui("🧮 Material", reverse("materials", args=[self.p.pk]))}

    # ---------- stages and diary ----------
    def get_stage_checklist(self, a):
        from checks.models import Check

        stage = a.get("stage") if a.get("stage") in STAGE_CODES else self.p.current_stage
        items = []
        for it in ChecklistItem.objects.filter(stage=stage).select_related("rule"):
            last = Check.objects.filter(project=self.p, item=it).first()
            items.append({"code": it.code, "title": it.title_en, "method": it.method, "rule": it.rule.rule_id if it.rule else None,
                          "how": it.photo_guide_en, "last_result": last.status if last else "not checked"})
        return {"stage": stage, "items": items, "ui": _ui("📷 Checks", reverse("check_stage", args=[self.p.pk, stage]))}

    def set_stage_status(self, a):
        ps = ProjectStage.objects.filter(project=self.p, stage=a.get("stage")).first()
        if not ps or a.get("status") not in dict(ProjectStage.STATUS_CHOICES):
            return {"ok": False, "error": "Unknown stage or status (finish setup first)."}
        ps.status = a["status"]
        if ps.status == ProjectStage.IN_PROGRESS and not ps.started_at:
            ps.started_at = timezone.now()
        if ps.status == ProjectStage.DONE:
            ps.completed_at = timezone.now()
        ps.save()
        self.p.refresh_current_stage()
        return {"ok": True, "stage": ps.stage, "status": ps.status, "current_stage": self.p.current_stage}

    def add_diary_entry(self, a):
        from diary.models import DiaryEntry

        kind = a.get("kind")
        try:
            date = dt.date.fromisoformat(a["date"]) if a.get("date") else timezone.localdate()
        except ValueError:
            return {"ok": False, "error": "date must be YYYY-MM-DD"}
        e = DiaryEntry(project=self.p, date=date, kind=kind, note=str(a.get("note") or "")[:500])
        if kind == "material":
            if a.get("material") not in MATERIALS + ["other"] or _dec(a.get("quantity")) is None:
                return {"ok": False, "error": "material and quantity are needed"}
            e.material, e.quantity = a["material"], _dec(a["quantity"])
        elif kind == "payment":
            if a.get("payment_type") not in ("labour", "material", "transport", "other") or not _dec(a.get("amount")):
                return {"ok": False, "error": "payment_type and amount are needed"}
            e.payment_type, e.amount, e.paid_to = a["payment_type"], int(_dec(a["amount"])), str(a.get("paid_to") or "")[:80]
        elif kind == "note":
            if not e.note:
                return {"ok": False, "error": "note text is needed"}
        else:
            return {"ok": False, "error": "kind must be material, payment or note"}
        e.save()
        return {"ok": True, "saved_entry": e.pk, "date": date.isoformat(), **self.get_diary_totals({}),
                "ui": _ui("📒 Diary", reverse("diary", args=[self.p.pk]))}

    def get_diary_totals(self, a):
        from calculator.service import latest_estimate
        from diary.totals import material_totals, payment_totals

        est = latest_estimate(self.p)
        mats = material_totals(self.p, est.materials if est else {})
        pays, total = payment_totals(self.p)
        return {"materials": [{k: (float(v) if isinstance(v, Decimal) else v) for k, v in m.items()} for m in mats],
                "payments": [{**r, "total": float(r["total"])} for r in pays], "total_paid": float(total)}


def handlers_for(project):
    t = Tools(project)
    return {spec["function"]["name"]: getattr(t, spec["function"]["name"]) for spec in TOOLS}
