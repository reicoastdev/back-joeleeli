from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.events.models import Event, EventMembership, InvitationCategory
from apps.guests.models import Guest
from apps.invitations.models import Invitation


@pytest.fixture
def event(db):
    starts_at = timezone.now() + timedelta(days=1)
    return Event.objects.create(
        name="Casamento Elisangela e Joel",
        starts_at=starts_at,
        rsvp_deadline=starts_at - timedelta(hours=1),
        timezone="America/Fortaleza",
        location="Fortaleza",
        status=Event.Status.ACTIVE,
    )


@pytest.fixture
def category(event):
    return InvitationCategory.objects.create(event=event, name="Família")


@pytest.fixture
def invitation(event, category):
    return Invitation.objects.create(
        event=event,
        category=category,
        description="Família Oliveira",
        responsible_name="José Oliveira",
        guest_limit=4,
        notes="Acesso pela entrada principal",
    )


@pytest.fixture
def guests(invitation):
    return [
        Guest.objects.create(invitation=invitation, name="Elisangela"),
        Guest.objects.create(invitation=invitation, name="Joel"),
        Guest.objects.create(invitation=invitation, name="Ana"),
    ]


@pytest.fixture
def supervisor(db):
    return User.objects.create_user(
        email="supervisor@example.com",
        password="correct-horse-battery-staple",
    )


@pytest.fixture
def membership(supervisor, event):
    return EventMembership.objects.create(user=supervisor, event=event)


@pytest.fixture
def authenticated_client(supervisor, membership):
    client = APIClient()
    login = client.post(
        "/api/v1/auth/login/",
        {
            "email": supervisor.email,
            "password": "correct-horse-battery-staple",
        },
        format="json",
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json()['access_token']}")
    return client


@pytest.fixture
def idempotency_headers():
    def headers(key="12345678-1234-5678-1234-567812345678"):
        return {"HTTP_IDEMPOTENCY_KEY": key}

    return headers
