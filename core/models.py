from django.conf import settings
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone


class AIUsage(models.Model):
    """Counts AI calls per user per day, so one user can not run up the bill."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    day = models.DateField(default=timezone.localdate)
    count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("user", "day")]

    @classmethod
    def take(cls, user) -> bool:
        """Reserve one AI call. False when today's limit is used up."""
        with transaction.atomic():
            row, _ = cls.objects.select_for_update().get_or_create(user=user, day=timezone.localdate())
            if row.count >= settings.AI_DAILY_LIMIT_PER_USER:
                return False
            cls.objects.filter(pk=row.pk).update(count=F("count") + 1)
        return True
