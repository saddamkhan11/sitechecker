from django.db import models

from projects.models import Project


class Plan(models.Model):
    """The room plan as JSON (see calculator.calc for the format). Every save is a new version."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="plans")
    version = models.PositiveIntegerField()
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version"]
        unique_together = [("project", "version")]

    def __str__(self):
        return f"Plan v{self.version} for project {self.project_id}"

    @classmethod
    def latest_for(cls, project):
        return cls.objects.filter(project=project).order_by("-version").first()

    @classmethod
    def save_new(cls, project, data):
        last = cls.latest_for(project)
        if last and last.data == data:
            return last
        return cls.objects.create(project=project, version=(last.version + 1 if last else 1), data=data)
