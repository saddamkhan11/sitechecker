from django.contrib import admin

from .models import ChecklistItem, Project, ProjectStage, Rate, Rule


@admin.register(Rule)
class RuleAdmin(admin.ModelAdmin):
    list_display = ["rule_id", "category", "title", "value", "unit", "engineer_reviewed", "updated_at"]
    list_filter = ["category", "engineer_reviewed"]
    list_editable = ["value", "engineer_reviewed"]
    search_fields = ["rule_id", "title", "text_en", "text_ur"]
    actions = ["mark_reviewed"]

    @admin.action(description="Mark selected rules as engineer reviewed")
    def mark_reviewed(self, request, queryset):
        queryset.update(engineer_reviewed=True)


@admin.register(Rate)
class RateAdmin(admin.ModelAdmin):
    list_display = ["material", "price", "unit", "city", "date_entered", "entered_by"]
    list_filter = ["material", "city"]
    date_hierarchy = "date_entered"


class StageInline(admin.TabularInline):
    model = ProjectStage
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "owner", "city", "room_length_ft", "room_width_ft", "current_stage", "in_scope", "created_at"]
    list_filter = ["current_stage", "in_scope", "city"]
    search_fields = ["name", "city", "owner__phone"]
    inlines = [StageInline]


@admin.register(ChecklistItem)
class ChecklistItemAdmin(admin.ModelAdmin):
    list_display = ["code", "stage", "order", "title_en", "method", "compare", "rule"]
    list_filter = ["stage", "method"]
    search_fields = ["code", "title_en", "title_ur"]
