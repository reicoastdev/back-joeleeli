from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from apps.events.models import Event, InvitationCategory


class Invitation(models.Model):
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    category = models.ForeignKey(
        InvitationCategory,
        on_delete=models.RESTRICT,
        related_name="invitations",
    )
    description = models.CharField(max_length=255)
    responsible_name = models.CharField(max_length=255)
    responsible_phone = models.CharField(max_length=32, blank=True)
    guest_limit = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    public_token = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        unique=True,
        editable=False,
    )
    public_token_issued_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~Q(description=""),
                name="invitations_invitation_description_not_empty",
            ),
            models.CheckConstraint(
                condition=~Q(responsible_name=""),
                name="invitations_invitation_responsible_name_not_empty",
            ),
            models.CheckConstraint(
                condition=Q(guest_limit__gte=1),
                name="invitations_invitation_guest_limit_gte_1",
            ),
            models.CheckConstraint(
                condition=Q(public_token__isnull=True) | ~Q(public_token=""),
                name="invitations_public_token_not_empty",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        public_token__isnull=True,
                        public_token_issued_at__isnull=True,
                    )
                    | Q(
                        public_token__isnull=False,
                        public_token_issued_at__isnull=False,
                    )
                ),
                name="invitations_public_token_issued_state_valid",
            ),
        ]

    def __str__(self):
        return self.description

    def clean(self):
        super().clean()
        if self.public_token == "":
            raise ValidationError({"public_token": "The public token cannot be empty."})
        if (self.public_token is None) != (self.public_token_issued_at is None):
            raise ValidationError(
                {
                    "public_token": (
                        "The public token and its issuance timestamp must be set "
                        "or cleared together."
                    )
                }
            )

        if self.event_id is not None and self.category_id is not None:
            category = self._state.fields_cache.get("category")
            if category is not None:
                category_event_id = category.event_id
            else:
                category_event_id = (
                    InvitationCategory.objects.filter(pk=self.category_id)
                    .values_list("event_id", flat=True)
                    .first()
                )
            if category_event_id is not None and category_event_id != self.event_id:
                raise ValidationError(
                    {"category": "The category must belong to the invitation event."}
                )

        if self.pk is not None and self.guest_limit is not None:
            active_guest_count = self.guests.filter(is_active=True).count()
            if self.guest_limit < active_guest_count:
                raise ValidationError(
                    {
                        "guest_limit": (
                            "The guest limit cannot be lower than the number of "
                            "active guests."
                        )
                    }
                )


class InvitationResponse(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "CONFIRMED", "Confirmed"
        DECLINED = "DECLINED", "Declined"

    invitation = models.ForeignKey(
        Invitation,
        on_delete=models.CASCADE,
        related_name="rsvp_responses",
    )
    status = models.CharField(max_length=9, choices=Status)
    guest_names = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["CONFIRMED", "DECLINED"]),
                name="invitations_response_status_valid",
            )
        ]

    def __str__(self):
        return f"RSVP response #{self.pk}: {self.status}"
