from datetime import timedelta

import pytest
from django.utils import timezone

from apps.events.models import Event, InvitationCategory
from apps.invitations.models import Invitation


@pytest.fixture
def event(db):
    starts_at = timezone.now() + timedelta(days=30)
    return Event.objects.create(
        name="Renovação de Votos — Elisangela e Joel",
        starts_at=starts_at,
        rsvp_deadline=starts_at - timedelta(days=7),
        timezone="America/Fortaleza",
        location="Fortaleza, Ceará",
    )


@pytest.fixture
def category(event):
    return InvitationCategory.objects.create(event=event, name="Família")


@pytest.fixture
def invitation_values(event, category):
    return {
        "event": event,
        "category": category,
        "description": "Família Oliveira",
        "responsible_name": "João Oliveira",
        "guest_limit": 4,
    }


@pytest.fixture
def invitation(invitation_values):
    return Invitation.objects.create(**invitation_values)
