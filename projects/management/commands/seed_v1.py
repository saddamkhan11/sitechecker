from decimal import Decimal

from django.core.management.base import BaseCommand

from projects.models import ChecklistItem, Rule
from projects.seed_data import CHECKLIST, RULES


class Command(BaseCommand):
    help = "Load the Version 1 Rules table and stage checklists. Existing reviewed rules are not overwritten."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Overwrite rules even if an engineer reviewed them")

    def handle(self, *args, force=False, **opts):
        made = updated = skipped = 0
        for rid, cat, title, value, unit, en, ur, src in RULES:
            existing = Rule.objects.filter(rule_id=rid).first()
            if existing and existing.engineer_reviewed and not force:
                skipped += 1
                continue
            _, created = Rule.objects.update_or_create(
                rule_id=rid,
                defaults=dict(
                    category=cat, title=title, value=Decimal(str(value)) if value is not None else None,
                    unit=unit, text_en=en, text_ur=ur, source=src,
                ),
            )
            made += created
            updated += not created
        for code, stage, order, method, compare, t_en, t_ur, g_en, g_ur, look, rid, labels in CHECKLIST:
            ChecklistItem.objects.update_or_create(
                code=code,
                defaults=dict(
                    stage=stage, order=order, method=method, compare=compare, title_en=t_en, title_ur=t_ur,
                    photo_guide_en=g_en, photo_guide_ur=g_ur, look_for=look,
                    rule=Rule.objects.filter(rule_id=rid).first(), measure_labels=labels,
                ),
            )
        self.stdout.write(self.style.SUCCESS(
            f"Rules: {made} new, {updated} updated, {skipped} kept (engineer reviewed). Checklist items: {len(CHECKLIST)}."
        ))
        self.stdout.write(self.style.WARNING("All seeded rules are PENDING ENGINEER REVIEW. Review them in /admin before launch."))
