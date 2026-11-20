from django.db import models

from projects.models import ChecklistItem, Project


def photo_path(instance, filename):
    return f"checks/p{instance.project_id}/{instance.item.code}/{filename}"


class Check(models.Model):
    PENDING, GREEN, YELLOW, RED, ERROR = "pending", "green", "yellow", "red", "error"
    STATUS_CHOICES = [
        (PENDING, "Checking..."),
        (GREEN, "No problem seen"),
        (YELLOW, "Not sure - check again"),
        (RED, "Problem seen"),
        (ERROR, "Could not check"),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="checks")
    item = models.ForeignKey(ChecklistItem, on_delete=models.PROTECT, related_name="checks")
    photo = models.ImageField(upload_to=photo_path, null=True, blank=True)
    measurements = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    reason = models.TextField(blank=True)
    confidence = models.FloatField(null=True, blank=True)
    advice = models.TextField(blank=True, help_text="One line to say to the mistri")
    retake = models.BooleanField(default=False, help_text="Low confidence: ask for a new photo")
    rule_snapshot = models.TextField(blank=True, help_text="The rule text used for this check")
    model_used = models.CharField(max_length=60, blank=True)
    captured_at = models.DateTimeField(null=True, blank=True, help_text="Phone time when taken (queued uploads)")
    SOURCE_CHOICES = [("camera", "Live camera in the app"), ("camera_app", "Phone camera app"), ("gallery", "Gallery (not verified)")]
    photo_source = models.CharField(max_length=12, choices=SOURCE_CHOICES, blank=True)
    photo_taken_at = models.DateTimeField(null=True, blank=True, help_text="Date inside the photo (EXIF) for gallery photos")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Server time - the trusted timestamp")
    checked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.item.code} {self.status} ({self.created_at:%Y-%m-%d})"

    @property
    def gallery_old_days(self):
        """For a gallery photo: how many days older than its upload it is (None if unknown or fresh)."""
        if self.photo_source != "gallery" or not self.photo_taken_at:
            return None
        days = (self.created_at - self.photo_taken_at).days
        return days if days >= 2 else None

    @property
    def colour(self):
        return {"green": "success", "yellow": "warning", "red": "danger", "error": "secondary"}.get(self.status, "info")
