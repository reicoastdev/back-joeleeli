from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.events.models import Event
from apps.guests.models import Guest


class CheckIn(models.Model):
    event = models.ForeignKey(
        Event,
        on_delete=models.PROTECT,
        related_name="check_ins",
    )
    guest = models.ForeignKey(
        Guest,
        on_delete=models.PROTECT,
        related_name="check_ins",
    )
    checked_in_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="performed_check_ins",
    )
    checked_in_at = models.DateTimeField()
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cancelled_check_ins",
    )
    cancellation_reason = models.TextField(null=True, blank=True)  # noqa: DJ001
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-checked_in_at", "-pk")
        constraints = [
            models.UniqueConstraint(
                fields=("guest",),
                condition=Q(cancelled_at__isnull=True),
                name="checkins_one_active_per_guest",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        cancelled_at__isnull=True,
                        cancelled_by__isnull=True,
                        cancellation_reason__isnull=True,
                    )
                    | Q(
                        cancelled_at__isnull=False,
                        cancelled_by__isnull=False,
                        cancellation_reason__isnull=False,
                    )
                    & ~Q(cancellation_reason="")
                ),
                name="checkins_cancellation_state_consistent",
            ),
        ]

    def __str__(self):
        return f"Check-in #{self.pk}: {self.guest}"

    def clean(self):
        super().clean()
        if self.guest_id and self.event_id:
            guest_event_id = self.guest.invitation.event_id
            if guest_event_id != self.event_id:
                raise ValidationError(
                    {"event": "Event must match the guest invitation."}
                )
        cancellation_values = (
            self.cancelled_at,
            self.cancelled_by_id,
            self.cancellation_reason,
        )
        if any(value is not None for value in cancellation_values):
            if not all(value is not None for value in cancellation_values):
                raise ValidationError("Cancellation fields must be set together.")
            if not self.cancellation_reason.strip():
                raise ValidationError(
                    {"cancellation_reason": "Cancellation reason is required."}
                )

    @property
    def is_active(self):
        return self.cancelled_at is None


class CheckInOperation(models.Model):
    class Action(models.TextChoices):
        INDIVIDUAL = "INDIVIDUAL", "Individual check-in"
        GROUP = "GROUP", "Group check-in"
        CANCEL = "CANCEL", "Cancel check-in"

    event = models.ForeignKey(
        Event,
        on_delete=models.PROTECT,
        related_name="check_in_operations",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="check_in_operations",
    )
    idempotency_key = models.UUIDField()
    action = models.CharField(max_length=10, choices=Action)
    request_fingerprint = models.CharField(max_length=64)
    response_payload = models.JSONField(null=True, blank=True)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("event", "user", "idempotency_key"),
                name="checkins_operation_event_user_key_unique",
            ),
            models.CheckConstraint(
                condition=(
                    Q(response_payload__isnull=True, response_status__isnull=True)
                    | Q(response_payload__isnull=False, response_status__isnull=False)
                ),
                name="checkins_operation_response_state_consistent",
            ),
        ]

    def __str__(self):
        return f"{self.action} {self.idempotency_key}"
