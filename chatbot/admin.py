from django.contrib import admin

from .models import ChatMessage


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ["created_at", "project", "role", "source", "language", "short"]
    list_filter = ["role", "source", "language"]
    search_fields = ["text"]

    @admin.display(description="Text")
    def short(self, obj):
        return obj.text[:80]
