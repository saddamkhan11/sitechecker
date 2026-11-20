import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from calculator.calc import default_plan
from core.i18n import tr, ui_language
from projects.models import rule_values
from projects.views import get_project

from . import geometry
from .layout import add_default_openings, relayout
from .models import Plan
from .plan_checks import check_plan, clean_plan
from .service import PlanRefused, save_plan


def _plan_for(project):
    plan = Plan.latest_for(project)
    if plan is None and project.room_length_ft:
        plan = Plan.save_new(project, default_plan(project.room_length_ft, project.room_width_ft))
    return plan


@login_required
def editor(request, project_id):
    project = get_project(request, project_id)
    plan = _plan_for(project)
    if plan is None:
        return redirect("chat", project_id=project.pk)
    data = geometry.normalize(plan.data)
    return render(request, "plans/editor.html", {
        "project": project, "plan": plan, "plan_data": data, "findings": check_plan(data, rule_values()),
        "room_types": [(k, tr(v[0], ui_language(request))) for k, v in geometry.ROOM_TYPES.items()],
    })


def _body(request):
    return clean_plan(json.loads(request.body or "{}"))


@login_required
@require_POST
def save(request, project_id):
    """Save from the editor. Out-of-scope plans are saved but shown with red engineer warnings."""
    project = get_project(request, project_id)
    try:
        plan, findings = save_plan(project, json.loads(request.body or "{}"), allow_scope_errors=True)
    except (PlanRefused, ValueError) as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    return JsonResponse({"ok": True, "version": plan.version, "findings": findings, "summary": geometry.summary(plan.data)})


@login_required
@require_POST
def check(request, project_id):
    get_project(request, project_id)
    try:
        data = _body(request)
    except (ValueError, KeyError, TypeError) as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    return JsonResponse({"ok": True, "findings": check_plan(data, rule_values()), "summary": geometry.summary(data)})


@login_required
@require_POST
def arrange(request, project_id):
    """Auto-arrange: re-pack the rooms the user has, and place doors and windows again."""
    get_project(request, project_id)
    try:
        data = _body(request)
        mode = request.GET.get("mode", "layout")
        if mode == "openings":
            data["openings"] = [o for o in data["openings"] if o["room"] in {r["id"] for r in data["rooms"]}]
            out = add_default_openings(data, rule_values())
        else:
            out = relayout(data, rule_values())
    except (ValueError, KeyError, TypeError) as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    return JsonResponse({"ok": True, "plan": out, "findings": check_plan(out, rule_values())})


@login_required
def print_view(request, project_id):
    project = get_project(request, project_id)
    plan = _plan_for(project)
    if plan is None:
        return redirect("chat", project_id=project.pk)
    rules = rule_values()
    data = geometry.normalize(plan.data)
    bearing = rules.get("OPN-01", 8)
    rooms = geometry.room_map(data)
    openings = [{**o, "room_name": rooms.get(o.get("room"), {}).get("name", ""), "lintel_in": float(o["width_in"]) + 2 * bearing}
                for o in data.get("openings", [])]
    return render(request, "plans/print.html", {
        "project": project, "plan": plan, "plan_data": data, "openings": openings, "summary": geometry.summary(data),
        "findings": check_plan(data, rules), "rules": rules,
    })
