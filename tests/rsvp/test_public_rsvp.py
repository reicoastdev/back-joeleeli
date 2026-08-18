from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.events.models import Event
from apps.guests.models import Guest
from apps.invitations.models import InvitationResponse
from apps.invitations.public_links import revoke_public_token


def active_guest_names(invitation):
    return list(
        invitation.guests.filter(is_active=True)
        .order_by("pk")
        .values_list("name", flat=True)
    )


@pytest.mark.django_db
def test_get_public_rsvp_returns_only_required_pending_state(
    api_client,
    rsvp_url,
    active_event,
    public_invitation,
    public_token,
):
    response = api_client.get(rsvp_url)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "event": {
            "name": active_event.name,
            "starts_at": active_event.starts_at.isoformat().replace("+00:00", "Z"),
            "timezone": active_event.timezone,
            "location": active_event.location,
            "rsvp_deadline": active_event.rsvp_deadline.isoformat().replace(
                "+00:00", "Z"
            ),
        },
        "invitation": {
            "description": public_invitation.description,
            "responsible_name": public_invitation.responsible_name,
            "guest_limit": public_invitation.guest_limit,
        },
        "rsvp": {
            "status": "PENDING",
            "guests": [],
            "can_respond": True,
        },
    }
    rendered = response.content.decode()
    assert public_token not in rendered
    assert public_invitation.responsible_phone not in rendered
    assert public_invitation.notes not in rendered


@pytest.mark.django_db
def test_get_remains_available_after_deadline(
    api_client,
    rsvp_url,
    active_event,
):
    active_event.rsvp_deadline = timezone.now() - timedelta(seconds=1)
    active_event.save(update_fields=["rsvp_deadline", "updated_at"])

    response = api_client.get(rsvp_url)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["rsvp"]["can_respond"] is False


@pytest.mark.django_db
def test_invalid_and_revoked_tokens_return_same_generic_404(
    api_client,
    public_invitation,
    public_token,
):
    invalid_response = api_client.get(
        reverse("public-rsvp", kwargs={"token": "unknown-public-token"})
    )
    revoke_public_token(public_invitation.pk)
    revoked_response = api_client.get(
        reverse("public-rsvp", kwargs={"token": public_token})
    )

    assert invalid_response.status_code == status.HTTP_404_NOT_FOUND
    assert revoked_response.status_code == status.HTTP_404_NOT_FOUND
    assert invalid_response.json() == revoked_response.json()
    assert public_token not in revoked_response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("invitation_active", "event_status"),
    [
        (False, Event.Status.ACTIVE),
        (True, Event.Status.DRAFT),
        (True, Event.Status.FINALIZED),
        (True, Event.Status.CANCELLED),
    ],
)
def test_inactive_invitation_or_unavailable_event_returns_404(
    api_client,
    rsvp_url,
    public_invitation,
    active_event,
    invitation_active,
    event_status,
):
    public_invitation.is_active = invitation_active
    public_invitation.save(update_fields=["is_active", "updated_at"])
    active_event.status = event_status
    active_event.save(update_fields=["status", "updated_at"])

    response = api_client.get(rsvp_url)

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_confirmed_rsvp_trims_names_allows_duplicates_and_appends_history(
    api_client,
    rsvp_url,
    public_invitation,
):
    response = api_client.put(
        rsvp_url,
        {
            "status": "CONFIRMED",
            "guests": ["  João Oliveira  ", "João Oliveira"],
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["rsvp"] == {
        "status": "CONFIRMED",
        "guests": ["João Oliveira", "João Oliveira"],
        "can_respond": True,
    }
    assert active_guest_names(public_invitation) == [
        "João Oliveira",
        "João Oliveira",
    ]
    history = InvitationResponse.objects.get(invitation=public_invitation)
    assert history.status == InvitationResponse.Status.CONFIRMED
    assert history.guest_names == ["João Oliveira", "João Oliveira"]


@pytest.mark.django_db
def test_partial_confirmation_is_valid(api_client, rsvp_url, public_invitation):
    response = api_client.put(
        rsvp_url,
        {"status": "CONFIRMED", "guests": ["Maria Oliveira"]},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert len(active_guest_names(public_invitation)) == 1
    assert len(active_guest_names(public_invitation)) < public_invitation.guest_limit


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload",
    [
        {"status": "CONFIRMED", "guests": []},
        {"status": "CONFIRMED", "guests": ["   "]},
        {
            "status": "CONFIRMED",
            "guests": ["A", "B", "C", "D", "E"],
        },
        {"status": "DECLINED", "guests": ["João"]},
        {"status": "UNKNOWN", "guests": []},
    ],
)
def test_invalid_payload_does_not_change_composition_or_history(
    api_client,
    rsvp_url,
    public_invitation,
    payload,
):
    Guest.objects.create(invitation=public_invitation, name="Guest original")

    response = api_client.put(rsvp_url, payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert active_guest_names(public_invitation) == ["Guest original"]
    assert not InvitationResponse.objects.filter(invitation=public_invitation).exists()


@pytest.mark.django_db
def test_declined_rsvp_accepts_missing_guests_and_deactivates_all(
    api_client,
    rsvp_url,
    public_invitation,
):
    Guest.objects.bulk_create(
        [
            Guest(invitation=public_invitation, name="João"),
            Guest(invitation=public_invitation, name="Maria"),
        ]
    )

    response = api_client.put(
        rsvp_url,
        {"status": "DECLINED"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["rsvp"]["status"] == "DECLINED"
    assert response.json()["rsvp"]["guests"] == []
    assert active_guest_names(public_invitation) == []
    history = InvitationResponse.objects.get(invitation=public_invitation)
    assert history.guest_names == []


@pytest.mark.django_db
def test_rsvp_transitions_preserve_snapshots_and_use_latest_status(
    api_client,
    rsvp_url,
    public_invitation,
):
    submissions = [
        {"status": "CONFIRMED", "guests": ["João", "Maria"]},
        {"status": "CONFIRMED", "guests": ["Ana"]},
        {"status": "DECLINED", "guests": []},
        {"status": "CONFIRMED", "guests": ["Carlos"]},
    ]

    for payload in submissions:
        response = api_client.put(rsvp_url, payload, format="json")
        assert response.status_code == status.HTTP_200_OK

    history = list(
        InvitationResponse.objects.filter(invitation=public_invitation).order_by("pk")
    )
    assert [(item.status, item.guest_names) for item in history] == [
        ("CONFIRMED", ["João", "Maria"]),
        ("CONFIRMED", ["Ana"]),
        ("DECLINED", []),
        ("CONFIRMED", ["Carlos"]),
    ]
    assert active_guest_names(public_invitation) == ["Carlos"]

    current_response = api_client.get(rsvp_url)
    assert current_response.json()["rsvp"]["status"] == "CONFIRMED"
    assert current_response.json()["rsvp"]["guests"] == ["Carlos"]


@pytest.mark.django_db
def test_identical_confirmation_keeps_guests_and_still_appends_response(
    api_client,
    rsvp_url,
    public_invitation,
):
    payload = {"status": "CONFIRMED", "guests": ["João", "Maria"]}
    first_response = api_client.put(rsvp_url, payload, format="json")
    original_guest_ids = list(
        public_invitation.guests.filter(is_active=True)
        .order_by("pk")
        .values_list("pk", flat=True)
    )

    second_response = api_client.put(rsvp_url, payload, format="json")

    assert first_response.status_code == status.HTTP_200_OK
    assert second_response.status_code == status.HTTP_200_OK
    assert (
        list(
            public_invitation.guests.filter(is_active=True)
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        == original_guest_ids
    )
    assert InvitationResponse.objects.filter(invitation=public_invitation).count() == 2


@pytest.mark.django_db
def test_put_after_deadline_returns_stable_conflict_without_changes(
    api_client,
    rsvp_url,
    active_event,
    public_invitation,
):
    active_event.rsvp_deadline = timezone.now() - timedelta(seconds=1)
    active_event.save(update_fields=["rsvp_deadline", "updated_at"])

    response = api_client.put(
        rsvp_url,
        {"status": "CONFIRMED", "guests": ["João"]},
        format="json",
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {"code": "rsvp_closed"}
    assert active_guest_names(public_invitation) == []
    assert not InvitationResponse.objects.filter(invitation=public_invitation).exists()


@pytest.mark.django_db
def test_invalid_token_takes_precedence_over_payload_validation(api_client):
    response = api_client.put(
        reverse("public-rsvp", kwargs={"token": "unknown-public-token"}),
        {"status": "CONFIRMED", "guests": []},
        format="json",
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
