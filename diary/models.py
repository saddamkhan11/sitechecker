from django.db import models
from django.utils import timezone

from projects.models import Project


def diary_photo_path(instance, filename):
    return f"diary/p{instance.project_id}/{filename}"


class DiaryEntry(models.Model):
    MATERIAL, PAYMENT, NOTE, PHOTO = "material", "payment", "note", "photo"
    KIND_CHOICES = [(MATERIAL, "Material received"), (PAYMENT, "Payment"), (NOTE, "Note"), (PHOTO, "Photo")]
    MATERIAL_CHOICES = [
        ("brick", "Bricks (nos)"), ("cement", "Cement (bags)"), ("sand", "Sand (cft)"),
        ("crush", "Crush (cft)"), ("steel", "Steel (kg)"), ("other", "Other"),
    ]
    PAYMENT_CHOICES = [("labour", "Mistri / labour"), ("material", "Material"), ("transport", "Transport"), ("other", "Other")]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="diary")
    date = models.DateField(default=timezone.localdate)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    material = models.CharField(max_length=10, choices=MATERIAL_CHOICES, blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    payment_type = models.CharField(max_length=10, choices=PAYMENT_CHOICES, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, help_text="Rupees")
    paid_to = models.CharField(max_length=80, blank=True)
    note = models.TextField(blank=True)
    photo = models.ImageField(upload_to=diary_photo_path, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name_plural = "diary entries"

    def __str__(self):
        return f"{self.date} {self.kind} {self.material or self.payment_type}"
