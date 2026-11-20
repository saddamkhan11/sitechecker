"""Saving plans: one place that validates, checks the rules and keeps the project in step."""
from projects.models import rule_values

from . import geometry
from .models import Plan
from .plan_checks import check_plan, clean_plan, has_scope_error


class PlanRefused(ValueError):
    """The plan breaks a scope rule (needs an engineer) or is not a valid plan."""

    def __init__(self, message, findings=None):
        super().__init__(message)
        self.findings = findings or []


def save_plan(project, data, allow_scope_errors=False):
    """Clean, check and save a new plan version. Returns (plan, findings)."""
    try:
        clean = clean_plan(data)
    except (ValueError, KeyError, TypeError) as e:
        raise PlanRefused(f"Plan not valid: {e}")
    findings = check_plan(clean, rule_values())
    scope = has_scope_error(findings)
    if scope and not allow_scope_errors:
        raise PlanRefused("This needs an engineer: " + " ".join(f["en"] for f in scope), findings)
    plan = Plan.save_new(project, clean)
    sync_project(project, clean)
    return plan, findings


def sync_project(project, plan_data):
    """Keep the project's summary fields in step with the plan."""
    p = geometry.normalize(plan_data)
    rooms = p["rooms"]
    if len(rooms) == 1:
        r = rooms[0]
        project.room_length_ft = round(max(r["length_in"], r["width_in"]) / 12, 2)
        project.room_width_ft = round(min(r["length_in"], r["width_in"]) / 12, 2)
        project.project_type = r["type"] if r["type"] in ("washroom", "kitchen") else "room"
    else:
        _, _, box = geometry.footprint(p)
        project.room_length_ft = round((box[2] - box[0]) / 12, 2)
        project.room_width_ft = round((box[3] - box[1]) / 12, 2)
        project.project_type = "house"
    if p.get("plot"):
        project.plot_length_ft = round(p["plot"]["length_in"] / 12, 2)
        project.plot_width_ft = round(p["plot"]["width_in"] / 12, 2)
    project.save(update_fields=["room_length_ft", "room_width_ft", "project_type", "plot_length_ft", "plot_width_ft"])
    if project.onboarded:
        project.ensure_stages()
