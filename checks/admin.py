from django.contrib import admin

from .models import Check


@admin.register(Check)
class CheckAdmin(admin.ModelAdmin):
    list_display = ["created_at", "project", "item", "status", "confidence", "retake", "model_used"]
    list_filter = ["status", "item__stage", "retake"]
    search_fields = ["item__code", "reason"]
    readonly_fields = ["created_at", "checked_at", "captured_at"]
