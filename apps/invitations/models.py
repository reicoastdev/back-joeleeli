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
        ]

    def __str__(self):
        return self.description

    def clean(self):
        super().clean()
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
