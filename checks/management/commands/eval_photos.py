"""Measure photo-check accuracy on labelled site photos (plan module 4 'done when').

Put labelled photos here (folder is git-ignored):

    evals/photos/<ITEM_CODE>/good/*.jpg     work that matches the rule
    evals/photos/<ITEM_CODE>/bad/*.jpg      work that breaks the rule

e.g. evals/photos/SST-C3/bad/no_cover_blocks_1.jpg

    python manage.py eval_photos

The number that matters is WRONG GREENS: a "bad" photo shown green.
"""
import json
from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.utils import timezone

from checks.photos import normalise
from core import ai_service
from projects.models import ChecklistItem


class Command(BaseCommand):
    help = "Run the AI photo check on labelled test photos and report wrong-green rate."

    def handle(self, *args, **opts):
        if not ai_service.ai_available():
            raise CommandError("Set OPENAI_API_KEY first.")
        root = Path(settings.BASE_DIR / "evals" / "photos")
        if not root.exists():
            raise CommandError(f"Put labelled photos in {root}/<ITEM_CODE>/good|bad/")
        rows, counts = [], {}
        for item_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            item = ChecklistItem.objects.filter(code=item_dir.name).select_related("rule").first()
            if not item:
                self.stderr.write(f"skip {item_dir.name}: no such checklist item")
                continue
            for label in ("good", "bad"):
                for f in sorted((item_dir / label).glob("*.*")) if (item_dir / label).exists() else []:
                    with f.open("rb") as fh:
                        data = normalise(fh).read()
                    try:
                        r = ai_service.check_photo(image_bytes=data, mime="image/jpeg", item_title=item.title_en,
                                                   look_for=item.look_for, rule_line=item.rule.as_prompt_line() if item.rule else "",
                                                   facts={}, language="en")
                        status = r.status if r.confidence >= settings.PHOTO_MIN_CONFIDENCE and r.photo_usable else "yellow"
                    except ai_service.AIUnavailable as e:
                        status, r = "error", None
                        self.stderr.write(f"{f.name}: {e}")
                    counts[(label, status)] = counts.get((label, status), 0) + 1
                    rows.append({"item": item.code, "file": f.name, "label": label, "status": status,
                                 "reason": r.reason if r else "", "confidence": r.confidence if r else None})
                    self.stdout.write(f"{item.code} {label:4} -> {status:6} {f.name}")
        bad = sum(v for (lab, _), v in counts.items() if lab == "bad")
        wrong_green = counts.get(("bad", "green"), 0)
        good = sum(v for (lab, _), v in counts.items() if lab == "good")
        good_green = counts.get(("good", "green"), 0)
        out = Path(settings.BASE_DIR / "evals" / "results")
        out.mkdir(parents=True, exist_ok=True)
        (out / f"photos-{timezone.now():%Y%m%d-%H%M}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
        self.stdout.write("")
        self.stdout.write(f"Photos: {len(rows)} ({good} good, {bad} bad)")
        self.stdout.write(f"Counts: {dict((f'{a}->{b}', v) for (a, b), v in sorted(counts.items()))}")
        if bad:
            self.stdout.write(self.style.WARNING(f"WRONG GREEN rate: {wrong_green}/{bad} = {wrong_green / bad:.1%}  <- agree the limit with the engineer"))
        if good:
            self.stdout.write(f"Good photos shown green: {good_green}/{good} = {good_green / good:.1%}")
