from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.events.models import Event, InvitationCategory
from apps.invitations.models import Invitation
from apps.invitations.public_links import ensure_public_token


@pytest.fixture
def active_event(db):
    starts_at = timezone.now() + timedelta(days=30)
    return Event.objects.create(
        name="Renovação de Votos — Elisangela e Joel",
        starts_at=starts_at,
        rsvp_deadline=starts_at - timedelta(days=7),
        timezone="America/Fortaleza",
        location="Fortaleza, Ceará",
        status=Event.Status.ACTIVE,
    )


@pytest.fixture
def category(active_event):
    return InvitationCategory.objects.create(event=active_event, name="Família")


@pytest.fixture
def public_invitation(active_event, category):
    return Invitation.objects.create(
        event=active_event,
        category=category,
        description="Família Oliveira",
        responsible_name="João Oliveira",
        responsible_phone="+55 85 99999-9999",
        guest_limit=4,
        notes="Informação interna",
    )


@pytest.fixture
def public_token(public_invitation):
    return ensure_public_token(public_invitation.pk)


@pytest.fixture
def rsvp_url(public_token):
    return reverse("public-rsvp", kwargs={"token": public_token})


@pytest.fixture
def api_client():
    return APIClient()
