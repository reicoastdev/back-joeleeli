from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.events.models import Event


@pytest.mark.django_db
def test_create_event(event_values):
    event = Event.objects.create(**event_values)

    assert event.name == event_values["name"]
    assert event.starts_at == event_values["starts_at"]
    assert event.rsvp_deadline == event_values["rsvp_deadline"]
    assert event.timezone == "America/Fortaleza"
    assert event.location == event_values["location"]


def test_event_default_status(event):
    assert event.status == Event.Status.DRAFT


def test_event_timestamps_are_timezone_aware(event):
    assert timezone.is_aware(event.created_at)
    assert timezone.is_aware(event.updated_at)
    assert event.updated_at >= event.created_at


def test_event_accepts_valid_iana_timezone(event):
    event.full_clean()


@pytest.mark.django_db
def test_event_rejects_invalid_iana_timezone(event_values):
    event_values["timezone"] = "-03:00"
    event = Event(**event_values)

    with pytest.raises(ValidationError) as exc_info:
        event.full_clean()

    assert "timezone" in exc_info.value.message_dict


@pytest.mark.django_db
def test_event_rejects_rsvp_deadline_after_start(event_values):
    event_values["rsvp_deadline"] = event_values["starts_at"] + timedelta(hours=1)
    event = Event(**event_values)

    with pytest.raises(ValidationError) as exc_info:
        event.full_clean()

    assert "rsvp_deadline" in exc_info.value.message_dict


@pytest.mark.django_db
def test_database_rejects_rsvp_deadline_after_start(event_values):
    event_values["rsvp_deadline"] = event_values["starts_at"] + timedelta(hours=1)

    with pytest.raises(IntegrityError), transaction.atomic():
        Event.objects.create(**event_values)


@pytest.mark.django_db
def test_database_rejects_invalid_event_status(event_values):
    event_values["status"] = "UNKNOWN"

    with pytest.raises(IntegrityError), transaction.atomic():
        Event.objects.create(**event_values)


@pytest.mark.django_db
def test_event_rejects_empty_name(event_values):
    event_values["name"] = ""
    event = Event(**event_values)

    with pytest.raises(ValidationError) as exc_info:
        event.full_clean()

    assert "name" in exc_info.value.message_dict


def test_event_string_representation(event):
    assert str(event) == event.name
