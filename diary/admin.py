from django.contrib import admin

from .models import DiaryEntry


@admin.register(DiaryEntry)
class DiaryEntryAdmin(admin.ModelAdmin):
    list_display = ["date", "project", "kind", "material", "quantity", "payment_type", "amount"]
    list_filter = ["kind", "material", "payment_type"]
    date_hierarchy = "date"
