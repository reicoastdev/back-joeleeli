import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.events.models import Event, InvitationCategory


def create_second_event(event_values):
    return Event.objects.create(
        **{
            **event_values,
            "name": "Segundo evento",
            "location": "Recife, Pernambuco",
        }
    )


def test_create_invitation_category(event):
    category = InvitationCategory.objects.create(event=event, name="Padrinhos")

    assert category.name == "Padrinhos"


def test_invitation_category_belongs_to_event(event):
    category = InvitationCategory.objects.create(event=event, name="Família")

    assert category.event == event
    assert event.invitation_categories.get() == category


def test_invitation_category_is_active_by_default(event):
    category = InvitationCategory.objects.create(event=event, name="Convidados")

    assert category.is_active is True


@pytest.mark.django_db
def test_same_category_name_is_allowed_for_different_events(event, event_values):
    second_event = create_second_event(event_values)

    InvitationCategory.objects.create(event=event, name="Padrinhos")
    second_category = InvitationCategory.objects.create(
        event=second_event,
        name="Padrinhos",
    )

    assert second_category.event == second_event


def test_duplicate_category_name_is_rejected_for_same_event(event):
    InvitationCategory.objects.create(event=event, name="Padrinhos")

    with pytest.raises(IntegrityError), transaction.atomic():
        InvitationCategory.objects.create(event=event, name="Padrinhos")


def test_category_uniqueness_is_case_insensitive(event):
    InvitationCategory.objects.create(event=event, name="Padrinhos")

    with pytest.raises(IntegrityError), transaction.atomic():
        InvitationCategory.objects.create(event=event, name="PADRINHOS")


def test_deleting_event_deletes_its_categories(event):
    category = InvitationCategory.objects.create(event=event, name="Colaboradores")
    category_id = category.pk

    event.delete()

    assert not InvitationCategory.objects.filter(pk=category_id).exists()


def test_invitation_category_rejects_empty_name(event):
    category = InvitationCategory(event=event, name="")

    with pytest.raises(ValidationError) as exc_info:
        category.full_clean()

    assert "name" in exc_info.value.message_dict


def test_invitation_category_string_representation(event):
    category = InvitationCategory.objects.create(event=event, name="Outros")

    assert str(category) == "Outros"
