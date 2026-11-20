"""Glue between the Django models and the pure calculator."""
from projects.models import Rate, rule_values

from . import calc
from .models import Estimate


def constants():
    """All numeric rules; the calculator picks the ones it needs by rule ID."""
    return rule_values()


def current_plan_dict(project):
    from plans.models import Plan

    plan = Plan.latest_for(project)
    if plan:
        return plan.data, plan.version
    if project.room_length_ft and project.room_width_ft:
        return calc.default_plan(project.room_length_ft, project.room_width_ft), 0
    return None, 0


def build_estimate(project, save=True):
    """Run the calculator on the latest plan and price it with the newest rates for the city."""
    data, version = current_plan_dict(project)
    if data is None:
        return None
    quantities = calc.calculate(data, constants())
    rates = Rate.latest_for_city(project.city)
    rates_used = {m: {"price": float(r.effective_price), "unit": r.unit, "date": r.date_entered.isoformat()} for m, r in rates.items()}
    cost = calc.cost(quantities["materials"], {m: v["price"] for m, v in rates_used.items()})
    est = Estimate(project=project, plan_version=version, quantities=quantities, rates_used=rates_used, cost=cost)
    last = project.estimates.first()
    if last and last.mistri_demand:
        est.mistri_demand = last.mistri_demand
    if save:
        if last and last.quantities == quantities and last.rates_used == rates_used:
            return last
        est.save()
    return est


def latest_estimate(project):
    return project.estimates.first() or build_estimate(project)
