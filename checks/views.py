from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.ai_service import ai_available
from core.models import AIUsage
from projects.models import ChecklistItem, ProjectStage
from projects.stages import STAGE_CODES
from projects.views import get_project

from . import measure
from .models import Check
from .photos import BadPhoto, normalise, taken_at
from .tasks import run_photo_check


def _latest_by_item(project, stage=None):
    qs = Check.objects.filter(project=project).select_related("item").order_by("created_at")
    if stage:
        qs = qs.filter(item__stage=stage)
    latest = {}
    for c in qs:
        latest[c.item_id] = c
    return latest


@login_required
def stage_list(request, project_id):
    project = get_project(request, project_id)
    if not project.onboarded:
        return redirect("chat", project_id=project.pk)
    latest = _latest_by_item(project)
    stages = []
    for ps in project.stages.all():
        items = ChecklistItem.objects.filter(stage=ps.stage)
        stages.append({"ps": ps, "name": project.stage_name(ps.stage),
                       "items": [(i, latest.get(i.id)) for i in items]})
    return render(request, "checks/stages.html", {"project": project, "stages": stages})


@login_required
def stage_detail(request, project_id, stage):
    project = get_project(request, project_id)
    if stage not in STAGE_CODES:
        raise Http404
    ps = get_object_or_404(ProjectStage, project=project, stage=stage)
    latest = _latest_by_item(project, stage)
    items = [(i, latest.get(i.id)) for i in ChecklistItem.objects.filter(stage=stage)]
    curing_days = None
    if stage == "curing":
        curing_days = Check.objects.filter(project=project, item__code="CUR-C1").dates("created_at", "day").count()
    return render(request, "checks/stage.html", {
        "project": project, "ps": ps, "stage_name": project.stage_name(stage), "items": items, "curing_days": curing_days,
    })


@login_required
def item_detail(request, project_id, code):
    project = get_project(request, project_id)
    item = get_object_or_404(ChecklistItem, code=code)
    history = Check.objects.filter(project=project, item=item)[:10]
    return render(request, "checks/item.html", {
        "project": project, "item": item, "history": history, "ai_on": ai_available(),
        "lang": project.language, "stage_name": project.stage_name(item.stage),
    })


def _parse_dt(raw):
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _readings(request, n):
    vals = []
    for i in range(n):
        raw = request.POST.get(f"m{i}", "").strip()
        if raw == "":
            raise ValueError("Please fill every box.")
        vals.append(float(raw))
    return vals


def _plan_values(project):
    from plans.models import Plan

    plan = Plan.latest_for(project)
    return [float(plan.data["length_in"]), float(plan.data["width_in"])] if plan else None


@login_required
@require_POST
def submit(request, project_id, code):
    """Accepts a photo, typed measurements or tilt readings. Returns JSON for the offline queue, else redirects."""
    project = get_project(request, project_id)
    item = get_object_or_404(ChecklistItem, code=code)
    wants_json = request.headers.get("Accept", "").startswith("application/json")
    lang = project.language
    rule_val = float(item.rule.value) if item.rule and item.rule.value is not None else None

    def fail(msg):
        if wants_json:
            return JsonResponse({"ok": False, "error": msg}, status=400)
        messages.error(request, msg)
        return redirect("check_item", project_id=project.pk, code=code)

    check = Check(project=project, item=item, rule_snapshot=item.rule.as_prompt_line() if item.rule else "")
    check.captured_at = _parse_dt(request.POST.get("captured_at"))

    try:
        if item.method == ChecklistItem.MEASURE:
            vals = _readings(request, len(item.labels))
            if rule_val is None:
                return fail("This item has no rule value. Ask the admin to set it.")
            plan_vals = _plan_values(project) if item.compare == "plan" else None
            res = measure.compare(item.compare, vals, rule_val, item.rule.unit or "in", plan_vals)
            check.measurements = dict(zip(item.labels, vals))
        elif item.method == ChecklistItem.TILT:
            vals = [float(x) for x in request.POST.get("tilt", "").split(",") if x.strip()]
            if not vals:
                return fail("No tilt reading. Hold the phone on the wall and press Read.")
            res = measure.tilt(vals, rule_val or 0.5)
            check.measurements = {"tilt_deg": vals}
        else:
            res = None
    except ValueError as e:
        return fail(str(e))

    if res is not None:
        check.status = res["status"]
        check.reason = res["reason_ur"] if lang == "ur" else res["reason_en"] if lang == "en" else res["reason_roman"]
        check.advice = res["tell_mistri"]
        check.confidence = 1.0
        check.checked_at = timezone.now()
        check.model_used = "code"
        check.save()
    else:
        upload = request.FILES.get("photo")
        if not upload:
            return fail("Please take a photo first.")
        src = request.POST.get("source", "")
        check.photo_source = src if src in dict(Check.SOURCE_CHOICES) else "camera_app"
        if check.photo_source == "gallery":
            # The date inside the photo, else the file date the phone reports. Neither can be trusted fully,
            # which is why gallery photos are marked "not verified" on the result and the report.
            check.photo_taken_at = taken_at(upload) or _parse_dt(request.POST.get("taken_at"))
        try:
            check.photo = normalise(upload)
        except BadPhoto as e:
            return fail(str(e))
        if ai_available() and not AIUsage.take(request.user):
            check.status = Check.YELLOW
            check.reason = "Today's AI limit is used up. The photo is saved; check it again tomorrow."
            check.save()
        else:
            check.save()
            run_photo_check.delay(check.pk)

    if wants_json:
        return JsonResponse({"ok": True, "check_id": check.pk, "url": f"/p/{project.pk}/checks/result/{check.pk}/"})
    return redirect("check_result", project_id=project.pk, check_id=check.pk)


@login_required
def result(request, project_id, check_id):
    project = get_project(request, project_id)
    check = get_object_or_404(Check, pk=check_id, project=project)
    return render(request, "checks/result.html", {"project": project, "check": check, "item": check.item})


@login_required
def status_json(request, project_id, check_id):
    project = get_project(request, project_id)
    c = get_object_or_404(Check, pk=check_id, project=project)
    return JsonResponse({"status": c.status, "label": c.get_status_display(), "reason": c.reason,
                         "advice": c.advice, "confidence": c.confidence, "retake": c.retake})
