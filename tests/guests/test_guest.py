import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.guests.exceptions import InvitationCapacityExceeded
from apps.guests.models import Guest
from apps.guests.services import (
    add_guest,
    deactivate_guest,
    reactivate_guest,
    save_guest,
    update_guest_limit,
)


def test_create_guest(guest_values):
    guest = Guest.objects.create(**guest_values)

    assert guest.name == "Maria Oliveira"


def test_guest_belongs_to_invitation(guest, invitation):
    assert guest.invitation == invitation
    assert invitation.guests.get() == guest


def test_guest_is_active_by_default(guest):
    assert guest.is_active is True


def test_guest_timestamps_are_filled(guest):
    assert timezone.is_aware(guest.created_at)
    assert timezone.is_aware(guest.updated_at)
    assert guest.updated_at >= guest.created_at


def test_guest_string_representation(guest):
    assert str(guest) == "Maria Oliveira"


def test_empty_guest_name_is_rejected_by_validation(guest_values):
    guest_values["name"] = ""
    guest = Guest(**guest_values)

    with pytest.raises(ValidationError) as exc_info:
        guest.full_clean()

    assert "name" in exc_info.value.message_dict


def test_empty_guest_name_is_rejected_by_database(guest_values):
    guest_values["name"] = ""

    with pytest.raises(IntegrityError), transaction.atomic():
        Guest.objects.create(**guest_values)


def test_duplicate_guest_names_are_allowed(invitation):
    first_guest = add_guest(invitation_id=invitation.pk, name="João Silva")
    second_guest = add_guest(invitation_id=invitation.pk, name="João Silva")

    assert first_guest.name == second_guest.name
    assert first_guest.pk != second_guest.pk


def test_deleting_invitation_deletes_guests(invitation):
    guest = add_guest(invitation_id=invitation.pk, name="Maria Oliveira")
    guest_id = guest.pk

    invitation.delete()

    assert not Guest.objects.filter(pk=guest_id).exists()


def test_deleting_event_deletes_guests(event, invitation):
    guest = add_guest(invitation_id=invitation.pk, name="Maria Oliveira")
    guest_id = guest.pk

    event.delete()

    assert not Guest.objects.filter(pk=guest_id).exists()


def test_add_guest_within_capacity(invitation):
    guest = add_guest(invitation_id=invitation.pk, name="Maria Oliveira")

    assert guest.is_active is True
    assert invitation.guests.filter(is_active=True).count() == 1


def test_add_guest_in_last_available_slot(invitation):
    add_guest(invitation_id=invitation.pk, name="João Oliveira")
    last_guest = add_guest(invitation_id=invitation.pk, name="Maria Oliveira")

    assert last_guest.pk is not None
    assert invitation.guests.filter(is_active=True).count() == 2


def test_add_guest_above_capacity_is_rejected(invitation):
    add_guest(invitation_id=invitation.pk, name="João Oliveira")
    add_guest(invitation_id=invitation.pk, name="Maria Oliveira")

    with pytest.raises(InvitationCapacityExceeded):
        add_guest(invitation_id=invitation.pk, name="Ana Oliveira")

    assert invitation.guests.filter(is_active=True).count() == 2


def test_guest_full_clean_reports_exceeded_capacity(invitation):
    add_guest(invitation_id=invitation.pk, name="João Oliveira")
    add_guest(invitation_id=invitation.pk, name="Maria Oliveira")
    guest = Guest(invitation=invitation, name="Ana Oliveira")

    with pytest.raises(ValidationError) as exc_info:
        guest.full_clean()

    assert "invitation" in exc_info.value.message_dict


def test_inactive_guest_does_not_consume_capacity(invitation):
    update_guest_limit(invitation_id=invitation.pk, guest_limit=1)
    inactive_guest = add_guest(
        invitation_id=invitation.pk,
        name="Pedro Oliveira",
        is_active=False,
    )
    active_guest = add_guest(invitation_id=invitation.pk, name="Maria Oliveira")

    assert inactive_guest.is_active is False
    assert active_guest.is_active is True


def test_deactivating_guest_releases_capacity(invitation):
    update_guest_limit(invitation_id=invitation.pk, guest_limit=1)
    first_guest = add_guest(invitation_id=invitation.pk, name="João Oliveira")

    deactivate_guest(guest_id=first_guest.pk)
    second_guest = add_guest(invitation_id=invitation.pk, name="Maria Oliveira")

    assert second_guest.is_active is True
    assert invitation.guests.filter(is_active=True).count() == 1


def test_reactivating_guest_with_available_slot(invitation):
    guest = add_guest(
        invitation_id=invitation.pk,
        name="Maria Oliveira",
        is_active=False,
    )

    reactivated_guest = reactivate_guest(guest_id=guest.pk)

    assert reactivated_guest.is_active is True


def test_reactivating_guest_without_available_slot_is_rejected(invitation):
    update_guest_limit(invitation_id=invitation.pk, guest_limit=1)
    inactive_guest = add_guest(
        invitation_id=invitation.pk,
        name="Pedro Oliveira",
        is_active=False,
    )
    add_guest(invitation_id=invitation.pk, name="Maria Oliveira")

    with pytest.raises(InvitationCapacityExceeded):
        reactivate_guest(guest_id=inactive_guest.pk)

    inactive_guest.refresh_from_db()
    assert inactive_guest.is_active is False


def test_invitation_full_clean_rejects_limit_below_active_guests(invitation):
    add_guest(invitation_id=invitation.pk, name="João Oliveira")
    add_guest(invitation_id=invitation.pk, name="Maria Oliveira")
    invitation.guest_limit = 1

    with pytest.raises(ValidationError) as exc_info:
        invitation.full_clean()

    assert "guest_limit" in exc_info.value.message_dict


def test_increasing_guest_limit_is_allowed(invitation):
    add_guest(invitation_id=invitation.pk, name="João Oliveira")

    updated_invitation = update_guest_limit(
        invitation_id=invitation.pk,
        guest_limit=10,
    )

    assert updated_invitation.guest_limit == 10


def test_safe_limit_update_rejects_limit_below_active_guests(invitation):
    add_guest(invitation_id=invitation.pk, name="João Oliveira")
    add_guest(invitation_id=invitation.pk, name="Maria Oliveira")

    with pytest.raises(InvitationCapacityExceeded):
        update_guest_limit(invitation_id=invitation.pk, guest_limit=1)

    invitation.refresh_from_db()
    assert invitation.guest_limit == 2


def test_guest_cannot_be_moved_between_invitations(invitation, category, event):
    guest = add_guest(invitation_id=invitation.pk, name="Maria Oliveira")
    other_invitation = type(invitation).objects.create(
        event=event,
        category=category,
        description="João e Ana",
        responsible_name="João Silva",
        guest_limit=2,
    )
    guest.invitation = other_invitation

    with pytest.raises(ValidationError) as exc_info:
        save_guest(guest)

    assert "invitation" in exc_info.value.message_dict
