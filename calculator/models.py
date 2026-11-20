from django.db import models

from projects.models import Project


class Estimate(models.Model):
    """Quantities and cost for a project, with the mistri's demand for comparison."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="estimates")
    plan_version = models.PositiveIntegerField(default=1)
    quantities = models.JSONField(default=dict, help_text="Output of calculator.calc.calculate()")
    rates_used = models.JSONField(default=dict, help_text="{material: {price, unit, date}}")
    cost = models.JSONField(default=dict)
    mistri_demand = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Estimate {self.pk} for project {self.project_id} (plan v{self.plan_version})"

    @property
    def materials(self):
        return self.quantities.get("materials", {})
