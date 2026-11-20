from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from .stages import RULE_CATEGORY_CHOICES, STAGE_CHOICES, STAGE_CODES, STAGE_NAMES_ROMAN, STAGE_NAMES_UR


class Rule(models.Model):
    """One rule the engineer reviews. The AI quotes rules by rule_id; it never invents numbers."""

    rule_id = models.CharField(max_length=40, unique=True, help_text="e.g. FND-01")
    category = models.CharField(max_length=20, choices=RULE_CATEGORY_CHOICES)
    title = models.CharField(max_length=150)
    value = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    unit = models.CharField(max_length=30, blank=True)
    text_en = models.TextField()
    text_ur = models.TextField(blank=True)
    source = models.CharField(max_length=255, help_text="Where the rule comes from (BCP 2021 clause, engineer, practice)")
    engineer_reviewed = models.BooleanField(default=False)
    reviewed_by = models.CharField(max_length=120, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "rule_id"]

    def __str__(self):
        return f"{self.rule_id}: {self.title}"

    def text_for(self, language):
        if language == "ur" and self.text_ur:
            return self.text_ur
        return self.text_en

    def as_prompt_line(self):
        val = f" [value: {self.value.normalize()} {self.unit}]" if self.value is not None else ""
        return f"{self.rule_id} ({self.title}){val}: {self.text_en}" + (f" | Urdu: {self.text_ur}" if self.text_ur else "")


def rule_value(rule_id, default=None):
    """Numeric value of a rule as float, or default when it is missing."""
    r = Rule.objects.filter(rule_id=rule_id).only("value").first()
    if r is None or r.value is None:
        return default
    return float(r.value)


def rule_values(category=None):
    qs = Rule.objects.exclude(value__isnull=True)
    if category:
        qs = qs.filter(category=category)
    return {r.rule_id: float(r.value) for r in qs}


class Rate(models.Model):
    """A material price typed by the user. Prices change week to week, so each rate keeps its city and date."""

    BRICK, CEMENT, SAND, CRUSH, STEEL = "brick", "cement", "sand", "crush", "steel"
    MATERIAL_CHOICES = [
        (BRICK, "Bricks (per 1000)"),
        (CEMENT, "Cement (per 50 kg bag)"),
        (SAND, "Sand (per cft)"),
        (CRUSH, "Crush / bajri (per cft)"),
        (STEEL, "Steel (per kg)"),
    ]
    UNITS = {BRICK: "1000 nos", CEMENT: "bag", SAND: "cft", CRUSH: "cft", STEEL: "kg"}

    material = models.CharField(max_length=10, choices=MATERIAL_CHOICES)
    unit = models.CharField(max_length=20)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    city = models.CharField(max_length=60)
    date_entered = models.DateField(default=timezone.localdate)
    entered_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-date_entered", "-id"]

    PER_BRICK_LIMIT = 100  # a "per 1000" brick price below this was almost surely typed per brick

    @property
    def effective_price(self):
        """Price in the unit the calculator uses. Bricks are priced per 1000; 'Rs 18' means Rs 18 per brick."""
        if self.material == self.BRICK and self.price < self.PER_BRICK_LIMIT:
            return self.price * 1000
        return self.price

    def save(self, *args, **kwargs):
        if self.material == self.BRICK and self.price is not None and self.price < self.PER_BRICK_LIMIT:
            self.price = self.price * 1000  # typed per brick: store per 1000
        self.unit = self.unit or self.UNITS.get(self.material, "")
        self.city = (self.city or "").strip().title()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_material_display()} Rs {self.price} / {self.unit} - {self.city} ({self.date_entered})"

    @classmethod
    def latest_for_city(cls, city):
        """{material: Rate} with the newest rate per material for this city."""
        out = {}
        for rate in cls.objects.filter(city__iexact=(city or "").strip()):
            out.setdefault(rate.material, rate)
        return out


class Project(models.Model):
    WALL_BRICK = "brick"
    ROOF_RCC = "rcc_slab"
    TYPE_CHOICES = [
        ("room", "One room"),
        ("washroom", "Washroom"),
        ("kitchen", "Kitchen"),
        ("house", "Single-storey house"),
    ]

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="projects")
    name = models.CharField(max_length=100, default="My room")
    project_type = models.CharField(max_length=12, choices=TYPE_CHOICES, default="room")
    plot_length_ft = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="Plot front (width)")
    plot_width_ft = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="Plot depth")
    city = models.CharField(max_length=60, blank=True)
    room_length_ft = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    room_width_ft = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    wall_type = models.CharField(max_length=20, blank=True)
    roof_type = models.CharField(max_length=20, blank=True)
    budget_pkr = models.DecimalField(max_digits=14, decimal_places=0, null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    current_stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default=STAGE_CODES[0])
    onboarding_step = models.PositiveSmallIntegerField(default=0, help_text="0-7 while asking the starting questions, 8 = done")
    in_scope = models.BooleanField(default=True)
    scope_note = models.TextField(blank=True)
    LANGUAGE_CHOICES = [("roman", "Roman Urdu"), ("ur", "اردو"), ("en", "English")]
    VOICE_LANGUAGE_CHOICES = [("ur", "اردو / Roman Urdu"), ("en", "English")]
    language = models.CharField(max_length=8, choices=LANGUAGE_CHOICES, default="roman",
                                help_text="Language for typing and written replies")
    voice_language = models.CharField(max_length=8, choices=VOICE_LANGUAGE_CHOICES, default="ur",
                                      help_text="Language the user speaks in; spoken replies use it too")
    created_at = models.DateTimeField(auto_now_add=True)

    ONBOARDING_DONE = 8

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} - {self.city or 'city?'} ({self.owner.phone})"

    def get_absolute_url(self):
        return reverse("project_detail", args=[self.pk])

    @property
    def onboarded(self):
        return self.onboarding_step >= self.ONBOARDING_DONE

    @property
    def room_size_label(self):
        if self.room_length_ft and self.room_width_ft:
            return f"{float(self.room_length_ft):g} ft x {float(self.room_width_ft):g} ft"
        return "-"

    def stage_name(self, code=None, language=None):
        code = code or self.current_stage
        language = language or self.language
        if language == "ur":
            return STAGE_NAMES_UR.get(code, code)
        if language == "roman":
            return STAGE_NAMES_ROMAN.get(code, code)
        return dict(STAGE_CHOICES).get(code, code)

    @property
    def progress_pct(self):
        total = self.stages.count()
        return round(self.stages.filter(status=ProjectStage.DONE).count() / total * 100) if total else 0

    def default_name(self):
        """'Single-storey house, Karachi' in the owner's website language ('both' keeps it short in English)."""
        from core.i18n import tr

        lang = getattr(self.owner, "ui_language", "en")
        return f"{tr(self.get_project_type_display(), lang if lang in ('ur', 'roman') else 'en')}, {self.city}"

    def latest_plan(self):
        return self.plans.order_by("-version").first()

    def plan_summary(self):
        from plans import geometry

        plan = self.latest_plan()
        return geometry.summary(plan.data) if plan else None

    def has_wet_rooms(self):
        from plans import geometry

        plan = self.latest_plan()
        if plan:
            return any(r.get("type") in geometry.WET_TYPES for r in geometry.normalize(plan.data)["rooms"])
        return self.project_type in ("washroom", "kitchen")

    def facts(self):
        """Project facts given to the AI and printed on reports."""
        return {
            "project_type": self.get_project_type_display(),
            "city": self.city or None,
            "plot_ft": (f"{float(self.plot_length_ft):g} x {float(self.plot_width_ft):g}"
                        if self.plot_length_ft and self.plot_width_ft else None),
            "main_size_ft": self.room_size_label,
            "wall_type": self.wall_type or None,
            "roof_type": self.roof_type or None,
            "budget_pkr": int(self.budget_pkr) if self.budget_pkr else None,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "current_stage": self.get_current_stage_display(),
            "setup_complete": self.onboarded,
            "in_scope": self.in_scope,
            "plan": self.plan_summary(),
        }

    def ensure_stages(self):
        from .stages import WET_ONLY

        wet = self.has_wet_rooms()
        for order, code in enumerate(STAGE_CODES):
            if code in WET_ONLY and not wet:
                self.stages.filter(stage=code, status=ProjectStage.NOT_STARTED).delete()
                continue
            ps, created = ProjectStage.objects.get_or_create(project=self, stage=code, defaults={"order": order})
            if not created and ps.order != order:
                ps.order = order
                ps.save(update_fields=["order"])

    def refresh_current_stage(self):
        first_open = self.stages.exclude(status=ProjectStage.DONE).order_by("order").first()
        self.current_stage = first_open.stage if first_open else STAGE_CODES[-1]
        self.save(update_fields=["current_stage"])


class ProjectStage(models.Model):
    NOT_STARTED, IN_PROGRESS, DONE = "not_started", "in_progress", "done"
    STATUS_CHOICES = [(NOT_STARTED, "Not started"), (IN_PROGRESS, "In progress"), (DONE, "Done")]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="stages")
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES)
    order = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=NOT_STARTED)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["order"]
        unique_together = [("project", "stage")]

    def __str__(self):
        return f"{self.project_id} {self.stage}: {self.status}"


class ChecklistItem(models.Model):
    """One thing to check at a stage. Each item has a photo guide and its own AI prompt."""

    PHOTO, MEASURE, TILT = "photo", "measure", "tilt"
    METHOD_CHOICES = [
        (PHOTO, "Photo checked by AI"),
        (MEASURE, "User types measurements, code compares"),
        (TILT, "Phone tilt sensor held on the wall"),
    ]

    code = models.CharField(max_length=40, unique=True)
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES)
    order = models.PositiveSmallIntegerField(default=0)
    title_en = models.CharField(max_length=150)
    title_ur = models.CharField(max_length=150, blank=True)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES, default=PHOTO)
    photo_guide_en = models.TextField(blank=True, help_text="Which photo to take")
    photo_guide_ur = models.TextField(blank=True)
    look_for = models.TextField(blank=True, help_text="Prompt for the AI: what to look for in the photo")
    rule = models.ForeignKey(Rule, null=True, blank=True, on_delete=models.SET_NULL)
    COMPARE_CHOICES = [
        ("", "-"),
        ("diff", "Two readings must be equal within the rule value"),
        ("min", "Every reading must be at least the rule value"),
        ("max", "Every reading must be at most the rule value"),
        ("plan", "Readings must match the plan within the rule value"),
    ]
    compare = models.CharField(max_length=10, choices=COMPARE_CHOICES, blank=True)
    measure_labels = models.CharField(
        max_length=200, blank=True, help_text="For measure items: comma separated input labels, e.g. 'Diagonal 1 (in), Diagonal 2 (in)'"
    )

    class Meta:
        ordering = ["stage", "order"]

    def __str__(self):
        return f"{self.code}: {self.title_en}"

    def title_for(self, language):
        return self.title_ur if language == "ur" and self.title_ur else self.title_en

    def guide_for(self, language):
        return self.photo_guide_ur if language == "ur" and self.photo_guide_ur else self.photo_guide_en

    @property
    def labels(self):
        return [x.strip() for x in self.measure_labels.split(",") if x.strip()]


def to_decimal(v):
    return Decimal(str(v)) if v is not None else None
