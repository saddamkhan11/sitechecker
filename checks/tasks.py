import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from core import ai_service

from .models import Check

log = logging.getLogger(__name__)

RETAKE = {
    "roman": " Tasveer saaf nahi. Baraye meharbani nayi tasveer lein.",
    "ur": " تصویر واضح نہیں۔ براہ مہربانی نئی تصویر لیں۔",
    "en": " The photo is not clear enough. Please take a new photo.",
}
NO_AI = {
    "roman": "AI abhi dastiyab nahi. Tasveer save ho gayi hai; baad mein dobara check karein ya engineer ko dikhayein.",
    "ur": "اے آئی ابھی دستیاب نہیں۔ تصویر رکھ لی گئی ہے؛ بعد میں دوبارہ چیک کریں یا انجینئر کو دکھائیں۔",
    "en": "The AI is not available now. The photo is saved; check again later or show it to an engineer.",
}


@shared_task(bind=True, max_retries=2, default_retry_delay=20)
def run_photo_check(self, check_id: int):
    """Load the rule, send photo + rule + project facts to the AI, validate, save green/yellow/red."""
    check = Check.objects.select_related("item__rule", "project").get(pk=check_id)
    project, item = check.project, check.item
    lang = project.language
    rule = item.rule
    rule_line = rule.as_prompt_line() if rule else "(no rule linked)"
    check.rule_snapshot = rule_line

    if not ai_service.ai_available():
        check.status, check.reason, check.checked_at = Check.YELLOW, NO_AI.get(lang, NO_AI["en"]), timezone.now()
        check.retake = False
        check.save()
        return check.status

    try:
        with check.photo.open("rb") as f:
            data = f.read()
        res = ai_service.check_photo(
            image_bytes=data, mime="image/jpeg", item_title=item.title_en, look_for=item.look_for,
            rule_line=rule_line, facts=project.facts(), language=lang, measurements=check.measurements,
        )
    except ai_service.AIUnavailable as e:
        log.warning("photo check %s failed: %s", check_id, e)
        if not settings.CELERY_TASK_ALWAYS_EAGER and self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        check.status, check.reason, check.checked_at = Check.ERROR, NO_AI.get(lang, NO_AI["en"]), timezone.now()
        check.save()
        return check.status

    status = res.status
    retake = False
    if res.confidence < settings.PHOTO_MIN_CONFIDENCE or not res.photo_usable:
        # Low confidence never shows green or red: ask for a new photo.
        status, retake = Check.YELLOW, True
    check.status = status
    check.reason = res.reason + (RETAKE.get(lang, RETAKE["en"]) if retake else "")
    check.confidence = res.confidence
    check.advice = res.tell_mistri
    check.retake = retake
    check.model_used = f"{ai_service.provider()}:{ai_service.model('vision')}"
    check.checked_at = timezone.now()
    check.save()
    return check.status
