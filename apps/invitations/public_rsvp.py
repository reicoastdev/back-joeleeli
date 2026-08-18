from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.events.models import Event
from apps.guests.models import Guest

from .models import Invitation, InvitationResponse
from .public_links import PublicInvitationNotFound
from .serializers import PublicRSVPSubmissionSerializer


class RSVPClosedError(Exception):
    """Raised when a public RSVP can no longer be changed."""


def _public_invitation_not_found():
    return PublicInvitationNotFound("Public invitation was not found.")


def _available_invitation_queryset(*, lock=False):
    queryset = Invitation.objects.select_related("event")
    if lock:
        queryset = queryset.select_for_update(of=("self",))
    return queryset.filter(
        is_active=True,
        event__status=Event.Status.ACTIVE,
    )


def _get_available_invitation(token, *, lock=False):
    if not token:
        raise _public_invitation_not_found()

    try:
        return _available_invitation_queryset(lock=lock).get(public_token=token)
    except Invitation.DoesNotExist:
        raise _public_invitation_not_found() from None


def _active_guest_names(invitation):
    return list(
        invitation.guests.filter(is_active=True)
        .order_by("pk")
        .values_list("name", flat=True)
    )


def _current_status(invitation):
    latest_response = (
        invitation.rsvp_responses.order_by("-created_at", "-pk")
        .values_list("status", flat=True)
        .first()
    )
    return latest_response or "PENDING"


def _public_rsvp_data(invitation):
    event = invitation.event
    return {
        "event": {
            "name": event.name,
            "starts_at": event.starts_at,
            "timezone": event.timezone,
            "location": event.location,
            "rsvp_deadline": event.rsvp_deadline,
        },
        "invitation": {
            "description": invitation.description,
            "responsible_name": invitation.responsible_name,
            "guest_limit": invitation.guest_limit,
        },
        "rsvp": {
            "status": _current_status(invitation),
            "guests": _active_guest_names(invitation),
            "can_respond": timezone.now() <= event.rsvp_deadline,
        },
    }


def get_public_rsvp(token):
    invitation = _get_available_invitation(token)
    return _public_rsvp_data(invitation)


def _validate_submission(payload, invitation):
    serializer = PublicRSVPSubmissionSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    guest_names = serializer.validated_data["guests"]

    if len(guest_names) > invitation.guest_limit:
        raise serializers.ValidationError(
            {"guests": "The invitation guest limit was exceeded."},
            code="guest_limit_exceeded",
        )
    return serializer.validated_data


def _apply_guest_composition(invitation, *, status, guest_names):
    active_guests = Guest.objects.filter(
        invitation_id=invitation.pk,
        is_active=True,
    )
    current_names = list(active_guests.order_by("pk").values_list("name", flat=True))

    if status == InvitationResponse.Status.CONFIRMED:
        if current_names == guest_names:
            return
        active_guests.update(is_active=False, updated_at=timezone.now())
        Guest.objects.bulk_create(
            [Guest(invitation=invitation, name=name) for name in guest_names]
        )
        return

    active_guests.update(is_active=False, updated_at=timezone.now())


@transaction.atomic
def submit_public_rsvp(*, token, payload):
    invitation = _get_available_invitation(token, lock=True)
    if timezone.now() > invitation.event.rsvp_deadline:
        raise RSVPClosedError

    submission = _validate_submission(payload, invitation)
    status = submission["status"]
    guest_names = submission["guests"]

    _apply_guest_composition(
        invitation,
        status=status,
        guest_names=guest_names,
    )
    InvitationResponse.objects.create(
        invitation=invitation,
        status=status,
        guest_names=guest_names,
    )
    return _public_rsvp_data(invitation)
