from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.invitations.models import Invitation


class Guest(models.Model):
    invitation = models.ForeignKey(
        Invitation,
        on_delete=models.CASCADE,
        related_name="guests",
    )
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~Q(name=""),
                name="guests_guest_name_not_empty",
            )
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if not self.is_active or self.invitation_id is None:
            return

        invitation = self._state.fields_cache.get("invitation")
        if invitation is None:
            invitation = (
                Invitation.objects.only("guest_limit")
                .filter(pk=self.invitation_id)
                .first()
            )
        if invitation is None:
            return

        active_guests = Guest.objects.filter(
            invitation_id=self.invitation_id,
            is_active=True,
        )
        if self.pk is not None:
            active_guests = active_guests.exclude(pk=self.pk)

        if active_guests.count() >= invitation.guest_limit:
            raise ValidationError(
                {"invitation": "This invitation has no available guest slots."}
            )
