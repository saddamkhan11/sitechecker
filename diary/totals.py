"""Running totals for the diary, next to the estimate."""
from decimal import Decimal

from django.db.models import Sum

from .models import DiaryEntry

UNITS = {"brick": "nos", "cement": "bags", "sand": "cft", "crush": "cft", "steel": "kg"}
LABELS = {"brick": "Bricks", "cement": "Cement", "sand": "Sand", "crush": "Crush (bajri)", "steel": "Steel (sariya)"}


def material_totals(project, estimate_materials: dict, date_from=None, date_to=None):
    qs = project.diary.filter(kind=DiaryEntry.MATERIAL)
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    received = {r["material"]: r["total"] for r in qs.values("material").annotate(total=Sum("quantity"))}
    rows = []
    for mat, unit in UNITS.items():
        got = received.get(mat) or Decimal(0)
        est = estimate_materials.get(mat)
        pct = float(got) / est * 100 if est else None
        rows.append({"material": mat, "label": LABELS[mat], "unit": unit, "received": got, "estimate": est,
                     "pct": round(pct) if pct is not None else None, "over": bool(est and float(got) > est)})
    return rows


def payment_totals(project, date_from=None, date_to=None):
    qs = project.diary.filter(kind=DiaryEntry.PAYMENT)
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    by_type = {r["payment_type"]: r["total"] for r in qs.values("payment_type").annotate(total=Sum("amount"))}
    labels = dict(DiaryEntry.PAYMENT_CHOICES)
    rows = [{"type": t, "label": labels[t], "total": by_type.get(t) or 0} for t in labels]
    return rows, sum((r["total"] for r in rows), Decimal(0))
