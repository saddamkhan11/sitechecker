from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from projects.models import Rate, rule_value
from projects.views import get_project

from . import calc
from .service import build_estimate

LABELS = {
    "brick": ("Bricks", "اینٹیں", "nos"),
    "cement": ("Cement", "سیمنٹ", "bags"),
    "sand": ("Sand", "ریت", "cft"),
    "crush": ("Crush (bajri)", "بجری", "cft"),
    "steel": ("Steel (sariya)", "سریا", "kg"),
}


def _num(v):
    try:
        d = Decimal(str(v).replace(",", "").strip())
        return d if d >= 0 else None
    except (InvalidOperation, AttributeError):
        return None


@login_required
def materials(request, project_id):
    project = get_project(request, project_id)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "rates":
            n = 0
            for mat, _ in Rate.MATERIAL_CHOICES:
                price = _num(request.POST.get(f"rate_{mat}", ""))
                if price:
                    Rate.objects.create(material=mat, price=price, city=project.city, entered_by=request.user)
                    n += 1
            messages.success(request, f"{n} rate(s) saved for {project.city}.")
        elif action == "demand":
            est = build_estimate(project)
            demand = {}
            for mat in calc.MATERIALS:
                v = _num(request.POST.get(f"demand_{mat}", ""))
                if v is not None:
                    demand[mat] = float(v)
            est.mistri_demand = demand
            est.save(update_fields=["mistri_demand"])
            messages.success(request, "Mistri demand saved.")
        return redirect("materials", project_id=project.pk)

    est = build_estimate(project)
    if est is None:
        messages.info(request, "Finish the starting questions in the chat first.")
        return redirect("chat", project_id=project.pk)
    tolerance = rule_value("CALC-MISTRI-TOLERANCE", 10)
    comparison = calc.compare_demand(est.materials, est.mistri_demand, tolerance)
    rates = Rate.latest_for_city(project.city)
    rows = []
    for mat in calc.MATERIALS:
        en, ur, unit = LABELS[mat]
        rows.append({
            "key": mat, "en": en, "ur": ur, "unit": unit, "qty": est.materials.get(mat),
            "rate": rates.get(mat), "amount": est.cost["lines"].get(mat),
            "demand": est.mistri_demand.get(mat), "cmp": comparison.get(mat),
            "sections": {s: v.get(mat) for s, v in est.quantities["sections"].items()},
        })
    budget_diff = None
    if project.budget_pkr and est.cost["total"] and not est.cost["missing"]:
        budget_diff = est.cost["total"] - int(project.budget_pkr)
    return render(request, "calculator/materials.html", {
        "project": project, "est": est, "rows": rows, "tolerance": tolerance,
        "volumes": est.quantities["volumes"], "notes": est.quantities["notes"], "budget_diff": budget_diff,
    })
