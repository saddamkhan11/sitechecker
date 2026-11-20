from django.db import models

from projects.models import Project


class ChatMessage(models.Model):
    USER, ASSISTANT = "user", "assistant"
    ROLE_CHOICES = [(USER, "User"), (ASSISTANT, "Assistant")]
    SOURCES = [
        ("user", "User"), ("onboarding", "Starting questions"), ("scope", "Scope gate"),
        ("ai", "AI with rules"), ("rules", "Rules table (no AI)"), ("limit", "Daily limit"),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    text = models.TextField()
    source = models.CharField(max_length=12, choices=SOURCES, default="user")
    language = models.CharField(max_length=8, default="roman")
    meta = models.JSONField(default=dict, blank=True, help_text="Tools used, rule IDs, model")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.role}: {self.text[:60]}"
