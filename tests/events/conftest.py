from datetime import timedelta

import pytest
from django.utils import timezone

from apps.events.models import Event


@pytest.fixture
def event_values():
    starts_at = timezone.now() + timedelta(days=30)
    return {
        "name": "Renovação de Votos — Elisangela e Joel",
        "starts_at": starts_at,
        "rsvp_deadline": starts_at - timedelta(days=7),
        "timezone": "America/Fortaleza",
        "location": "Fortaleza, Ceará",
    }


@pytest.fixture
def event(db, event_values):
    return Event.objects.create(**event_values)
