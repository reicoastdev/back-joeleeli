from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower


def validate_iana_timezone(value):
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError, TypeError) as exc:
        raise ValidationError(
            "Enter a valid IANA timezone.", code="invalid_timezone"
        ) from exc


class Event(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active"
        FINALIZED = "FINALIZED", "Finalized"
        CANCELLED = "CANCELLED", "Cancelled"

    name = models.CharField(max_length=255)
    starts_at = models.DateTimeField()
    rsvp_deadline = models.DateTimeField()
    timezone = models.CharField(max_length=64, validators=[validate_iana_timezone])
    location = models.CharField(max_length=255)
    status = models.CharField(
        max_length=9,
        choices=Status,
        default=Status.DRAFT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~Q(name=""),
                name="events_event_name_not_empty",
            ),
            models.CheckConstraint(
                condition=~Q(location=""),
                name="events_event_location_not_empty",
            ),
            models.CheckConstraint(
                condition=Q(rsvp_deadline__lte=F("starts_at")),
                name="events_event_rsvp_deadline_lte_starts_at",
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "DRAFT",
                        "ACTIVE",
                        "FINALIZED",
                        "CANCELLED",
                    ]
                ),
                name="events_event_status_valid",
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if (
            self.rsvp_deadline is not None
            and self.starts_at is not None
            and self.rsvp_deadline > self.starts_at
        ):
            raise ValidationError(
                {
                    "rsvp_deadline": (
                        "The RSVP deadline must be before or equal to the event start."
                    )
                }
            )


class InvitationCategory(models.Model):
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="invitation_categories",
    )
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~Q(name=""),
                name="events_invitation_category_name_not_empty",
            ),
            models.UniqueConstraint(
                Lower("name"),
                "event",
                name="events_invitation_category_event_name_ci_unique",
            ),
        ]

    def __str__(self):
        return self.name


class EventMembership(models.Model):
    class Role(models.TextChoices):
        SUPERVISOR = "SUPERVISOR", "Supervisor"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="event_memberships",
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=10, choices=Role, default=Role.SUPERVISOR)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "event"),
                name="events_membership_user_event_unique",
            ),
            models.CheckConstraint(
                condition=Q(role="SUPERVISOR"),
                name="events_membership_role_supervisor",
            ),
        ]

    def __str__(self):
        return f"{self.user} — {self.event} ({self.role})"
