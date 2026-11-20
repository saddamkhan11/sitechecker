from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import ChecklistItem, Project, ProjectStage, Rule


def get_project(request, project_id):
    """Every project page goes through this: a user only sees their own projects."""
    return get_object_or_404(Project, pk=project_id, owner=request.user)


@login_required
def project_list(request):
    return render(request, "projects/list.html", {"projects": request.user.projects.all()})


@login_required
@require_POST
def project_new(request):
    project = Project.objects.create(owner=request.user, language=request.user.language,
                                     voice_language="en" if request.user.language == "en" else "ur",
                                     name=request.POST.get("name", "").strip() or "My room")
    return redirect("chat", project_id=project.pk)


@login_required
def project_detail(request, project_id):
    project = get_project(request, project_id)
    if not project.onboarded:
        return redirect("chat", project_id=project.pk)
    from checks.models import Check

    stages = []
    for ps in project.stages.all():
        items = ChecklistItem.objects.filter(stage=ps.stage)
        latest = {}
        for c in Check.objects.filter(project=project, item__stage=ps.stage).order_by("created_at"):
            latest[c.item_id] = c.status
        counts = {s: list(latest.values()).count(s) for s in ("green", "yellow", "red")}
        stages.append({"ps": ps, "name": project.stage_name(ps.stage), "total": items.count(),
                       "checked": len(latest), **counts})

    # dashboard figures
    from calculator.service import build_estimate
    from diary.totals import payment_totals

    done = sum(1 for s in stages if s["ps"].status == ProjectStage.DONE)
    current = next((s for s in stages if s["ps"].stage == project.current_stage), stages[0] if stages else None)
    est = build_estimate(project)  # fresh: picks up rates saved since the last estimate
    _, paid = payment_totals(project)
    summary = project.plan_summary() or {}
    return render(request, "projects/detail.html", {
        "project": project, "stages": stages, "done": done, "total_stages": len(stages),
        "pct": round(done / len(stages) * 100) if stages else 0, "current": current,
        "estimate_total": est.cost.get("total") if est and not est.cost.get("missing") else None,
        "rates_missing": bool(est and est.cost.get("missing")), "paid": paid, "summary": summary,
    })


@login_required
@require_POST
def stage_status(request, project_id, stage):
    project = get_project(request, project_id)
    ps = get_object_or_404(ProjectStage, project=project, stage=stage)
    status = request.POST.get("status")
    if status in dict(ProjectStage.STATUS_CHOICES):
        ps.status = status
        if status == ProjectStage.IN_PROGRESS and not ps.started_at:
            ps.started_at = timezone.now()
        if status == ProjectStage.DONE:
            ps.completed_at = timezone.now()
        ps.save()
        project.refresh_current_stage()
    return redirect(request.POST.get("next") or project.get_absolute_url())


@login_required
def rules_list(request, project_id):
    project = get_project(request, project_id)
    return render(request, "projects/rules.html", {"project": project, "rules": Rule.objects.all()})
