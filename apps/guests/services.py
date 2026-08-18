from django.core.exceptions import ValidationError
from django.db import transaction

from apps.invitations.models import Invitation

from .exceptions import InvitationCapacityExceeded
from .models import Guest


def _ensure_capacity(invitation, *, exclude_guest_id=None):
    active_guests = Guest.objects.filter(
        invitation_id=invitation.pk,
        is_active=True,
    )
    if exclude_guest_id is not None:
        active_guests = active_guests.exclude(pk=exclude_guest_id)

    if active_guests.count() >= invitation.guest_limit:
        raise InvitationCapacityExceeded(
            {"invitation": "This invitation has no available guest slots."}
        )


@transaction.atomic
def save_guest(guest):
    """Persist a Guest while serializing capacity changes by invitation."""
    if guest.invitation_id is None:
        guest.full_clean()
        guest.save()
        return guest

    current_guest = None
    invitation_id = guest.invitation_id
    if guest.pk is not None:
        current_invitation_id = Guest.objects.values_list(
            "invitation_id", flat=True
        ).get(pk=guest.pk)
        if current_invitation_id != invitation_id:
            raise ValidationError(
                {"invitation": "A guest cannot be moved between invitations."}
            )

    invitation = Invitation.objects.select_for_update().get(pk=invitation_id)

    if guest.pk is not None:
        current_guest = Guest.objects.select_for_update().get(pk=guest.pk)

    capacity_increases = guest.is_active and (
        current_guest is None or not current_guest.is_active
    )
    if capacity_increases:
        _ensure_capacity(invitation, exclude_guest_id=guest.pk)

    guest.invitation = invitation
    guest.full_clean()
    guest.save()
    return guest


def add_guest(*, invitation_id, name, is_active=True):
    guest = Guest(
        invitation_id=invitation_id,
        name=name,
        is_active=is_active,
    )
    return save_guest(guest)


@transaction.atomic
def _set_guest_active(*, guest_id, is_active):
    invitation_id = Guest.objects.values_list("invitation_id", flat=True).get(
        pk=guest_id
    )
    invitation = Invitation.objects.select_for_update().get(pk=invitation_id)
    guest = Guest.objects.select_for_update().get(pk=guest_id)

    if is_active and not guest.is_active:
        _ensure_capacity(invitation, exclude_guest_id=guest.pk)

    guest.invitation = invitation
    guest.is_active = is_active
    guest.full_clean()
    guest.save(update_fields=["is_active", "updated_at"])
    return guest


def deactivate_guest(*, guest_id):
    return _set_guest_active(guest_id=guest_id, is_active=False)


def reactivate_guest(*, guest_id):
    return _set_guest_active(guest_id=guest_id, is_active=True)


@transaction.atomic
def update_guest_limit(*, invitation_id, guest_limit):
    invitation = Invitation.objects.select_for_update().get(pk=invitation_id)
    active_guest_count = Guest.objects.filter(
        invitation_id=invitation.pk,
        is_active=True,
    ).count()
    if guest_limit < active_guest_count:
        raise InvitationCapacityExceeded(
            {
                "guest_limit": (
                    "The guest limit cannot be lower than the number of active guests."
                )
            }
        )

    invitation.guest_limit = guest_limit
    invitation.full_clean()
    invitation.save(update_fields=["guest_limit", "updated_at"])
    return invitation
