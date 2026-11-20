import datetime as dt

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from calculator.service import latest_estimate
from core.i18n import ui_language
from checks.models import Check
from checks.photos import BadPhoto, normalise
from projects.views import get_project

from .forms import DiaryForm
from .models import DiaryEntry
from .totals import material_totals, payment_totals


@login_required
def diary(request, project_id):
    project = get_project(request, project_id)
    if not project.onboarded:
        return redirect("chat", project_id=project.pk)
    form = DiaryForm(request.POST or None, request.FILES or None, initial={"date": timezone.localdate(), "kind": "material"},
                     ui_lang=ui_language(request))
    if request.method == "POST" and form.is_valid():
        entry = form.save(commit=False)
        entry.project = project
        if entry.photo:
            try:
                entry.photo = normalise(request.FILES["photo"])
            except BadPhoto as e:
                messages.error(request, str(e))
                return redirect("diary", project_id=project.pk)
        entry.save()
        messages.success(request, "Saved.")
        return redirect("diary", project_id=project.pk)
    est = latest_estimate(project)
    mats = material_totals(project, est.materials if est else {})
    pays, pay_total = payment_totals(project)
    return render(request, "diary/diary.html", {
        "project": project, "form": form, "entries": project.diary.all()[:60],
        "mats": mats, "pays": pays, "pay_total": pay_total, "any_over": any(m["over"] for m in mats),
    })


@login_required
@require_POST
def delete(request, project_id, entry_id):
    project = get_project(request, project_id)
    get_object_or_404(DiaryEntry, pk=entry_id, project=project).delete()
    messages.info(request, "Entry deleted.")
    return redirect("diary", project_id=project.pk)


@login_required
def report(request, project_id):
    """One-page report for a date range (default: the last 7 days). Print it to PDF from the browser."""
    project = get_project(request, project_id)
    today = timezone.localdate()

    def parse(name, default):
        try:
            return dt.date.fromisoformat(request.GET.get(name, ""))
        except ValueError:
            return default

    date_to = parse("to", today)
    date_from = parse("from", date_to - dt.timedelta(days=6))
    est = latest_estimate(project)
    entries = project.diary.filter(date__gte=date_from, date__lte=date_to).order_by("date", "created_at")
    pays, pay_total = payment_totals(project, date_from, date_to)
    checks = (Check.objects.filter(project=project, created_at__date__gte=date_from, created_at__date__lte=date_to)
              .select_related("item").order_by("created_at"))
    return render(request, "diary/report.html", {
        "project": project, "date_from": date_from, "date_to": date_to, "est": est,
        "mats_period": material_totals(project, est.materials if est else {}, date_from, date_to),
        "mats_all": material_totals(project, est.materials if est else {}),
        "pays": pays, "pay_total": pay_total, "entries": entries, "checks": checks, "today": today,
    })
