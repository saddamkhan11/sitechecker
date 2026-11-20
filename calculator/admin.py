from django.contrib import admin

from .models import Estimate


@admin.register(Estimate)
class EstimateAdmin(admin.ModelAdmin):
    list_display = ["id", "project", "plan_version", "created_at"]
    readonly_fields = ["quantities", "rates_used", "cost"]
