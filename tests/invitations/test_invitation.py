from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import RestrictedError
from django.utils import timezone

from apps.events.models import Event, InvitationCategory
from apps.invitations.models import Invitation


def create_second_event():
    starts_at = timezone.now() + timedelta(days=60)
    return Event.objects.create(
        name="Segundo evento",
        starts_at=starts_at,
        rsvp_deadline=starts_at - timedelta(days=10),
        timezone="America/Recife",
        location="Recife, Pernambuco",
    )


def test_create_invitation(invitation_values):
    invitation = Invitation.objects.create(**invitation_values)

    assert invitation.description == "Família Oliveira"
    assert invitation.responsible_name == "João Oliveira"
    assert invitation.guest_limit == 4


def test_invitation_belongs_to_event(invitation, event):
    assert invitation.event == event
    assert event.invitations.get() == invitation


def test_invitation_belongs_to_category(invitation, category):
    assert invitation.category == category
    assert category.invitations.get() == invitation


def test_invitation_is_active_by_default(invitation):
    assert invitation.is_active is True


def test_responsible_phone_can_be_empty(invitation):
    assert invitation.responsible_phone == ""


def test_notes_can_be_empty(invitation):
    assert invitation.notes == ""


def test_invitation_timestamps_are_filled(invitation):
    assert timezone.is_aware(invitation.created_at)
    assert timezone.is_aware(invitation.updated_at)
    assert invitation.updated_at >= invitation.created_at


def test_invitation_string_representation(invitation):
    assert str(invitation) == "Família Oliveira"


def test_guest_limit_accepts_one(invitation_values):
    invitation_values["guest_limit"] = 1
    invitation = Invitation(**invitation_values)

    invitation.full_clean()


def test_guest_limit_accepts_large_values(invitation_values):
    invitation_values["guest_limit"] = 1_000_000
    invitation = Invitation(**invitation_values)

    invitation.full_clean()


def test_guest_limit_zero_is_rejected_by_validation(invitation_values):
    invitation_values["guest_limit"] = 0
    invitation = Invitation(**invitation_values)

    with pytest.raises(ValidationError) as exc_info:
        invitation.full_clean()

    assert "guest_limit" in exc_info.value.message_dict


def test_guest_limit_zero_is_rejected_by_database(invitation_values):
    invitation_values["guest_limit"] = 0

    with pytest.raises(IntegrityError), transaction.atomic():
        Invitation.objects.create(**invitation_values)


def test_negative_guest_limit_is_rejected(invitation_values):
    invitation_values["guest_limit"] = -1
    invitation = Invitation(**invitation_values)

    with pytest.raises(ValidationError) as exc_info:
        invitation.full_clean()

    assert "guest_limit" in exc_info.value.message_dict


def test_empty_description_is_rejected_by_validation(invitation_values):
    invitation_values["description"] = ""
    invitation = Invitation(**invitation_values)

    with pytest.raises(ValidationError) as exc_info:
        invitation.full_clean()

    assert "description" in exc_info.value.message_dict


def test_empty_description_is_rejected_by_database(invitation_values):
    invitation_values["description"] = ""

    with pytest.raises(IntegrityError), transaction.atomic():
        Invitation.objects.create(**invitation_values)


def test_empty_responsible_name_is_rejected_by_validation(invitation_values):
    invitation_values["responsible_name"] = ""
    invitation = Invitation(**invitation_values)

    with pytest.raises(ValidationError) as exc_info:
        invitation.full_clean()

    assert "responsible_name" in exc_info.value.message_dict


def test_empty_responsible_name_is_rejected_by_database(invitation_values):
    invitation_values["responsible_name"] = ""

    with pytest.raises(IntegrityError), transaction.atomic():
        Invitation.objects.create(**invitation_values)


def test_duplicate_descriptions_are_allowed(invitation_values):
    first_invitation = Invitation.objects.create(**invitation_values)
    second_invitation = Invitation.objects.create(**invitation_values)

    assert first_invitation.description == second_invitation.description
    assert first_invitation.pk != second_invitation.pk


def test_category_from_same_event_is_accepted(invitation_values):
    invitation = Invitation(**invitation_values)

    invitation.full_clean()


def test_clean_reuses_loaded_category_without_query(
    invitation_values,
    django_assert_num_queries,
):
    invitation = Invitation(**invitation_values)

    with django_assert_num_queries(0):
        invitation.clean()


def test_category_from_another_event_is_rejected(event, invitation_values):
    second_event = create_second_event()
    other_category = InvitationCategory.objects.create(
        event=second_event,
        name="Família",
    )
    invitation_values["event"] = event
    invitation_values["category"] = other_category
    invitation = Invitation(**invitation_values)

    with pytest.raises(ValidationError) as exc_info:
        invitation.full_clean()

    assert "category" in exc_info.value.message_dict


def test_deleting_used_category_is_restricted(category, invitation):
    with pytest.raises(RestrictedError):
        category.delete()


def test_deleting_event_deletes_its_invitations(event, invitation):
    invitation_id = invitation.pk

    event.delete()

    assert not Invitation.objects.filter(pk=invitation_id).exists()


def test_deleting_event_deletes_its_categories(event, category, invitation):
    category_id = category.pk

    event.delete()

    assert not InvitationCategory.objects.filter(pk=category_id).exists()
