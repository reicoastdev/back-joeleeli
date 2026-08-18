from datetime import timedelta
from uuid import uuid4

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.checkins.models import CheckIn, CheckInOperation
from apps.events.models import Event, InvitationCategory
from apps.guests.models import Guest
from apps.invitations.models import Invitation


def guest_url(event, guest):
    return f"/api/v1/events/{event.pk}/check-in/guests/{guest.pk}/"


def invitation_url(event, invitation):
    return f"/api/v1/events/{event.pk}/check-in/invitations/{invitation.pk}/"


def cancel_url(event, check_in):
    return f"/api/v1/events/{event.pk}/check-in/check-ins/{check_in.pk}/cancel/"


@pytest.mark.django_db
def test_login_valid_invalid_inactive_and_active_memberships(
    supervisor, event, membership
):
    client = APIClient()
    success = client.post(
        "/api/v1/auth/login/",
        {"email": supervisor.email.upper(), "password": "correct-horse-battery-staple"},
        format="json",
    )

    assert success.status_code == status.HTTP_200_OK
    assert set(success.json()) == {"access_token", "expires_in", "user", "events"}
    assert 14_300 <= success.json()["expires_in"] <= 14_400
    assert success.json()["user"] == {"id": supervisor.pk, "email": supervisor.email}
    assert success.json()["events"] == [
        {"id": event.pk, "name": event.name, "role": "SUPERVISOR"}
    ]
    assert "refresh" not in success.json()

    membership.is_active = False
    membership.save(update_fields=("is_active", "updated_at"))
    no_events = client.post(
        "/api/v1/auth/login/",
        {"email": supervisor.email, "password": "correct-horse-battery-staple"},
        format="json",
    )
    assert no_events.json()["events"] == []

    invalid = client.post(
        "/api/v1/auth/login/",
        {"email": supervisor.email, "password": "wrong"},
        format="json",
    )
    assert invalid.status_code == status.HTTP_401_UNAUTHORIZED

    supervisor.is_active = False
    supervisor.save(update_fields=("is_active",))
    inactive = client.post(
        "/api/v1/auth/login/",
        {"email": supervisor.email, "password": "correct-horse-battery-staple"},
        format="json",
    )
    assert inactive.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_event_access_requires_active_membership(
    supervisor, event, membership, authenticated_client
):
    url = f"/api/v1/events/{event.pk}/check-in/metrics/"
    membership.is_active = False
    membership.save(update_fields=("is_active", "updated_at"))
    assert authenticated_client.get(url).status_code == status.HTTP_403_FORBIDDEN

    membership.delete()
    assert authenticated_client.get(url).status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
@pytest.mark.parametrize("query", ["Família", "José", "Ana", "familia", "jose"])
def test_search_returns_invitation_for_description_responsible_guest_and_accents(
    authenticated_client, event, invitation, guests, query
):
    response = authenticated_client.get(
        f"/api/v1/events/{event.pk}/check-in/search/", {"q": query}
    )

    assert response.status_code == status.HTTP_200_OK
    assert [item["id"] for item in response.json()["results"]] == [invitation.pk]
    assert response.json()["results"][0]["description"] == "Família Oliveira"
    assert len(response.json()["results"][0]["participants_preview"]) <= 3


@pytest.mark.django_db
def test_presence_status_pending_partial_complete_and_metrics(
    authenticated_client, event, invitation, guests, idempotency_headers
):
    search_url = f"/api/v1/events/{event.pk}/check-in/search/"
    pending = authenticated_client.get(search_url, {"q": "Oliveira"}).json()["results"][
        0
    ]
    assert pending["presence_status"] == "PENDING"

    authenticated_client.post(
        guest_url(event, guests[0]),
        {},
        format="json",
        **idempotency_headers(str(uuid4())),
    )
    partial = authenticated_client.get(search_url, {"q": "Oliveira"}).json()["results"][
        0
    ]
    assert partial["presence_status"] == "PARTIAL"

    authenticated_client.post(
        invitation_url(event, invitation),
        {"guest_ids": [guests[1].pk, guests[2].pk]},
        format="json",
        **idempotency_headers(str(uuid4())),
    )
    complete = authenticated_client.get(search_url, {"q": "Oliveira"}).json()[
        "results"
    ][0]
    assert complete["presence_status"] == "COMPLETE"
    metrics = authenticated_client.get(
        f"/api/v1/events/{event.pk}/check-in/metrics/"
    ).json()
    assert metrics == {
        "confirmed_guests": 3,
        "present_guests": 3,
        "pending_guests": 0,
        "invitations_total": 1,
        "invitations_pending": 0,
        "invitations_partial": 0,
        "invitations_complete": 1,
    }


@pytest.mark.django_db
def test_invitation_without_active_guests_remains_pending(
    authenticated_client, event, invitation
):
    response = authenticated_client.get(
        f"/api/v1/events/{event.pk}/check-in/search/", {"q": "Oliveira"}
    )
    result = response.json()["results"][0]
    assert result["confirmed_count"] == 0
    assert result["presence_status"] == "PENDING"


@pytest.mark.django_db
def test_individual_duplicate_group_and_subset_create_individual_records(
    authenticated_client, event, invitation, guests, idempotency_headers
):
    individual = authenticated_client.post(
        guest_url(event, guests[0]),
        {},
        format="json",
        **idempotency_headers(str(uuid4())),
    )
    duplicate = authenticated_client.post(
        guest_url(event, guests[0]),
        {},
        format="json",
        **idempotency_headers(str(uuid4())),
    )
    subset = authenticated_client.post(
        invitation_url(event, invitation),
        {"guest_ids": [guests[1].pk]},
        format="json",
        **idempotency_headers(str(uuid4())),
    )

    assert individual.status_code == status.HTTP_201_CREATED
    assert duplicate.status_code == status.HTTP_200_OK
    assert duplicate.json()["result"] == "ALREADY_PRESENT"
    assert subset.status_code == status.HTTP_201_CREATED
    assert CheckIn.objects.filter(cancelled_at__isnull=True).count() == 2
    assert not CheckIn.objects.filter(guest=guests[2]).exists()

    group = authenticated_client.post(
        invitation_url(event, invitation),
        {"guest_ids": [guests[2].pk]},
        format="json",
        **idempotency_headers(str(uuid4())),
    )
    assert group.status_code == status.HTTP_201_CREATED
    assert set(CheckIn.objects.values_list("guest_id", flat=True)) == {
        guest.pk for guest in guests
    }


@pytest.mark.django_db
def test_group_rejects_guest_from_other_invitation_and_other_event_atomically(
    authenticated_client,
    event,
    category,
    invitation,
    guests,
    idempotency_headers,
):
    other_invitation = Invitation.objects.create(
        event=event,
        category=category,
        description="Amigos",
        responsible_name="Carlos",
        guest_limit=2,
    )
    external_same_event = Guest.objects.create(
        invitation=other_invitation, name="Carlos"
    )
    response = authenticated_client.post(
        invitation_url(event, invitation),
        {"guest_ids": [guests[0].pk, external_same_event.pk]},
        format="json",
        **idempotency_headers(str(uuid4())),
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert CheckIn.objects.count() == 0

    starts_at = timezone.now() + timedelta(days=2)
    other_event = Event.objects.create(
        name="Outro evento",
        starts_at=starts_at,
        rsvp_deadline=starts_at - timedelta(hours=1),
        timezone="America/Fortaleza",
        location="Fortaleza",
    )
    other_category = InvitationCategory.objects.create(
        event=other_event, name="Convidados"
    )
    other_event_invitation = Invitation.objects.create(
        event=other_event,
        category=other_category,
        description="Outro convite",
        responsible_name="Maria",
        guest_limit=1,
    )
    external_event = Guest.objects.create(
        invitation=other_event_invitation, name="Maria"
    )
    response = authenticated_client.post(
        invitation_url(event, invitation),
        {"guest_ids": [external_event.pk]},
        format="json",
        **idempotency_headers(str(uuid4())),
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert CheckIn.objects.count() == 0


@pytest.mark.django_db
def test_active_check_in_constraint_cancel_and_new_check_in(
    authenticated_client,
    supervisor,
    event,
    invitation,
    guests,
    idempotency_headers,
):
    checked_in_at = timezone.now()
    original = CheckIn.objects.create(
        event=event,
        guest=guests[0],
        checked_in_by=supervisor,
        checked_in_at=checked_in_at,
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        CheckIn.objects.create(
            event=event,
            guest=guests[0],
            checked_in_by=supervisor,
            checked_in_at=checked_in_at,
        )

    cancelled = authenticated_client.post(
        cancel_url(event, original),
        {"reason": "  Entrada registrada por engano  "},
        format="json",
        **idempotency_headers(str(uuid4())),
    )
    assert cancelled.status_code == status.HTTP_200_OK
    original.refresh_from_db()
    assert original.cancellation_reason == "Entrada registrada por engano"
    assert original.cancelled_by == supervisor

    second_cancel = authenticated_client.post(
        cancel_url(event, original),
        {"reason": "Outro motivo"},
        format="json",
        **idempotency_headers(str(uuid4())),
    )
    assert second_cancel.status_code == status.HTTP_409_CONFLICT

    new_entry = authenticated_client.post(
        guest_url(event, guests[0]),
        {},
        format="json",
        **idempotency_headers(str(uuid4())),
    )
    assert new_entry.status_code == status.HTTP_201_CREATED
    assert CheckIn.objects.filter(guest=guests[0]).count() == 2
    assert (
        CheckIn.objects.filter(guest=guests[0], cancelled_at__isnull=True).count() == 1
    )


@pytest.mark.django_db
def test_idempotency_replay_conflict_and_required_header(
    authenticated_client, event, invitation, guests, idempotency_headers
):
    key = str(uuid4())
    url = invitation_url(event, invitation)
    first = authenticated_client.post(
        url,
        {"guest_ids": [guests[0].pk, guests[1].pk]},
        format="json",
        **idempotency_headers(key),
    )
    replay = authenticated_client.post(
        url,
        {"guest_ids": [guests[0].pk, guests[1].pk]},
        format="json",
        **idempotency_headers(key),
    )
    conflict = authenticated_client.post(
        url,
        {"guest_ids": [guests[2].pk]},
        format="json",
        **idempotency_headers(key),
    )
    missing = authenticated_client.post(
        url, {"guest_ids": [guests[2].pk]}, format="json"
    )

    assert first.status_code == replay.status_code == status.HTTP_201_CREATED
    assert first.json() == replay.json()
    assert replay["Idempotency-Replayed"] == "true"
    assert conflict.status_code == status.HTTP_409_CONFLICT
    assert missing.status_code == status.HTTP_400_BAD_REQUEST
    assert CheckIn.objects.count() == 2
    assert CheckInOperation.objects.count() == 1


@pytest.mark.django_db
def test_cross_event_authorization_blocks_reads_and_all_mutations(
    supervisor, authenticated_client, event, invitation, guests, idempotency_headers
):
    starts_at = timezone.now() + timedelta(days=2)
    other_event = Event.objects.create(
        name="Evento protegido",
        starts_at=starts_at,
        rsvp_deadline=starts_at - timedelta(hours=1),
        timezone="America/Fortaleza",
        location="Fortaleza",
    )
    other_category = InvitationCategory.objects.create(
        event=other_event, name="Família"
    )
    other_invitation = Invitation.objects.create(
        event=other_event,
        category=other_category,
        description="Família Lima",
        responsible_name="Maria",
        guest_limit=1,
    )
    other_guest = Guest.objects.create(invitation=other_invitation, name="Maria")
    key = idempotency_headers(str(uuid4()))

    urls = [
        ("get", f"/api/v1/events/{other_event.pk}/check-in/metrics/", None),
        (
            "get",
            f"/api/v1/events/{other_event.pk}/check-in/search/?q=Maria",
            None,
        ),
        ("get", invitation_url(other_event, other_invitation), None),
        ("post", guest_url(other_event, other_guest), {}),
        (
            "post",
            invitation_url(other_event, other_invitation),
            {"guest_ids": [other_guest.pk]},
        ),
    ]
    for method, url, data in urls:
        response = getattr(authenticated_client, method)(
            url, data or {}, format="json", **key
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    assert CheckIn.objects.count() == 0
    assert CheckInOperation.objects.count() == 0


@pytest.mark.django_db
def test_operational_flow_has_no_delete_endpoint(
    authenticated_client, event, guests, supervisor
):
    check_in = CheckIn.objects.create(
        event=event,
        guest=guests[0],
        checked_in_by=supervisor,
        checked_in_at=timezone.now(),
    )
    response = authenticated_client.delete(cancel_url(event, check_in))
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert CheckIn.objects.filter(pk=check_in.pk).exists()


@pytest.mark.django_db
def test_user_without_event_receives_403(supervisor, event):
    token_client = APIClient()
    login = token_client.post(
        "/api/v1/auth/login/",
        {"email": supervisor.email, "password": "correct-horse-battery-staple"},
        format="json",
    )
    token_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {login.json()['access_token']}"
    )
    response = token_client.get(f"/api/v1/events/{event.pk}/check-in/metrics/")
    assert response.status_code == status.HTTP_403_FORBIDDEN
