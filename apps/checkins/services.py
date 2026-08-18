import unicodedata

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.guests.models import Guest
from apps.invitations.models import Invitation

from .models import CheckIn


class OperationError(Exception):
    def __init__(self, code, detail, status_code):
        self.payload = {"code": code, "detail": detail}
        self.status_code = status_code
        super().__init__(detail)


def _normalized(value):
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", value).casefold()
        if not unicodedata.combining(character)
    )


def _presence_status(confirmed_count, present_count):
    if confirmed_count > 0 and present_count == confirmed_count:
        return "COMPLETE"
    if present_count > 0:
        return "PARTIAL"
    return "PENDING"


def _check_in_summary(check_in):
    if check_in is None:
        return None
    return {
        "id": check_in.pk,
        "checked_in_at": check_in.checked_in_at.isoformat(),
        "checked_in_by": {
            "id": check_in.checked_in_by_id,
            "email": check_in.checked_in_by.email,
        },
    }


def _history_item(check_in):
    payload = _check_in_summary(check_in)
    payload.update(
        {
            "cancelled_at": (
                check_in.cancelled_at.isoformat() if check_in.cancelled_at else None
            ),
            "cancelled_by": (
                {
                    "id": check_in.cancelled_by_id,
                    "email": check_in.cancelled_by.email,
                }
                if check_in.cancelled_by_id
                else None
            ),
            "cancellation_reason": check_in.cancellation_reason,
        }
    )
    return payload


def invitation_detail(*, event_id, invitation_id):
    try:
        invitation = Invitation.objects.select_related("category").get(
            pk=invitation_id,
            event_id=event_id,
            is_active=True,
        )
    except Invitation.DoesNotExist:
        raise OperationError(
            "invitation_not_found", "Invitation was not found.", 404
        ) from None

    guests = list(
        Guest.objects.filter(invitation=invitation, is_active=True)
        .prefetch_related("check_ins__checked_in_by", "check_ins__cancelled_by")
        .order_by("pk")
    )
    participant_payloads = []
    present_count = 0
    for guest in guests:
        history = list(guest.check_ins.all())
        active = next((item for item in history if item.cancelled_at is None), None)
        present_count += int(active is not None)
        participant_payloads.append(
            {
                "id": guest.pk,
                "name": guest.name,
                "is_present": active is not None,
                "active_check_in": _check_in_summary(active),
                "check_in_history": [_history_item(item) for item in history],
            }
        )

    confirmed_count = len(guests)
    return {
        "id": invitation.pk,
        "description": invitation.description,
        "responsible_name": invitation.responsible_name,
        "category": {"id": invitation.category_id, "name": invitation.category.name},
        "notes": invitation.notes,
        "confirmed_count": confirmed_count,
        "present_count": present_count,
        "presence_status": _presence_status(confirmed_count, present_count),
        "guests": participant_payloads,
    }


def search_invitations(*, event_id, query):
    query = query.strip()
    if not query:
        return []
    invitations = (
        Invitation.objects.select_related("category")
        .filter(event_id=event_id, is_active=True)
        .filter(
            Q(description__unaccent__icontains=query)
            | Q(responsible_name__unaccent__icontains=query)
            | Q(guests__is_active=True, guests__name__unaccent__icontains=query)
        )
        .distinct()
        .order_by("description", "pk")
    )
    normalized_query = _normalized(query)
    results = []
    for invitation in invitations:
        guests = list(
            Guest.objects.filter(invitation=invitation, is_active=True)
            .prefetch_related("check_ins")
            .order_by("pk")
        )
        participants = []
        present_count = 0
        for guest in guests:
            is_present = any(
                item.cancelled_at is None for item in guest.check_ins.all()
            )
            present_count += int(is_present)
            participants.append(
                {
                    "id": guest.pk,
                    "name": guest.name,
                    "is_present": is_present,
                    "matched": normalized_query in _normalized(guest.name),
                }
            )
        ordered = sorted(participants, key=lambda item: not item["matched"])
        preview = []
        for item in ordered[:3]:
            item = item.copy()
            if not item["matched"]:
                item.pop("matched")
            preview.append(item)
        confirmed_count = len(guests)
        results.append(
            {
                "id": invitation.pk,
                "description": invitation.description,
                "responsible_name": invitation.responsible_name,
                "category": {
                    "id": invitation.category_id,
                    "name": invitation.category.name,
                },
                "confirmed_count": confirmed_count,
                "present_count": present_count,
                "presence_status": _presence_status(confirmed_count, present_count),
                "participants_preview": preview,
                "remaining_participants": max(confirmed_count - len(preview), 0),
            }
        )
    return results


@transaction.atomic
def check_in_guests(*, event_id, invitation_id, guest_ids, user):
    try:
        invitation = Invitation.objects.select_for_update().get(
            pk=invitation_id,
            event_id=event_id,
            is_active=True,
        )
    except Invitation.DoesNotExist:
        raise OperationError(
            "invitation_not_found", "Invitation was not found.", 404
        ) from None

    guests = list(
        Guest.objects.select_for_update()
        .filter(pk__in=guest_ids)
        .select_related("invitation")
        .order_by("pk")
    )
    if len(guests) != len(guest_ids):
        raise OperationError("invalid_guests", "One or more guests are invalid.", 400)
    if any(
        not guest.is_active
        or guest.invitation_id != invitation.pk
        or guest.invitation.event_id != event_id
        for guest in guests
    ):
        raise OperationError("invalid_guests", "One or more guests are invalid.", 400)

    active_guest_ids = set(
        CheckIn.objects.filter(
            guest_id__in=guest_ids,
            cancelled_at__isnull=True,
        ).values_list("guest_id", flat=True)
    )
    new_guest_ids = [guest.pk for guest in guests if guest.pk not in active_guest_ids]
    checked_in_at = timezone.now()
    CheckIn.objects.bulk_create(
        [
            CheckIn(
                event_id=event_id,
                guest_id=guest_id,
                checked_in_by=user,
                checked_in_at=checked_in_at,
            )
            for guest_id in new_guest_ids
        ]
    )
    return {
        "result": "CHECKED_IN" if new_guest_ids else "ALREADY_PRESENT",
        "checked_in_guest_ids": new_guest_ids,
        "already_present_guest_ids": sorted(active_guest_ids),
        "invitation": invitation_detail(
            event_id=event_id,
            invitation_id=invitation.pk,
        ),
    }, (201 if new_guest_ids else 200)


def check_in_guest(*, event_id, guest_id, user):
    guest = Guest.objects.select_related("invitation").filter(pk=guest_id).first()
    if guest is None or guest.invitation.event_id != event_id:
        raise OperationError("guest_not_found", "Guest was not found.", 404)
    return check_in_guests(
        event_id=event_id,
        invitation_id=guest.invitation_id,
        guest_ids=[guest_id],
        user=user,
    )


@transaction.atomic
def cancel_check_in(*, event_id, check_in_id, reason, user):
    try:
        check_in = (
            CheckIn.objects.select_for_update()
            .select_related("guest__invitation")
            .get(pk=check_in_id, event_id=event_id)
        )
    except CheckIn.DoesNotExist:
        raise OperationError(
            "check_in_not_found", "Check-in was not found.", 404
        ) from None
    if check_in.cancelled_at is not None:
        raise OperationError(
            "check_in_already_cancelled",
            "Check-in was already cancelled.",
            409,
        )
    reason = reason.strip()
    if not reason:
        raise OperationError(
            "cancellation_reason_required",
            "Cancellation reason is required.",
            400,
        )
    check_in.cancelled_at = timezone.now()
    check_in.cancelled_by = user
    check_in.cancellation_reason = reason
    check_in.full_clean()
    check_in.save(update_fields=("cancelled_at", "cancelled_by", "cancellation_reason"))
    return {
        "result": "CANCELLED",
        "invitation": invitation_detail(
            event_id=event_id,
            invitation_id=check_in.guest.invitation_id,
        ),
    }, 200


def event_metrics(*, event_id):
    active_invitations = Invitation.objects.filter(event_id=event_id, is_active=True)
    confirmed_guests = Guest.objects.filter(
        invitation__in=active_invitations,
        is_active=True,
    ).count()
    present_guests = CheckIn.objects.filter(
        event_id=event_id,
        guest__is_active=True,
        guest__invitation__is_active=True,
        cancelled_at__isnull=True,
    ).count()
    invitation_counts = {"PENDING": 0, "PARTIAL": 0, "COMPLETE": 0}
    for invitation_id in active_invitations.values_list("pk", flat=True):
        detail = invitation_detail(event_id=event_id, invitation_id=invitation_id)
        invitation_counts[detail["presence_status"]] += 1
    return {
        "confirmed_guests": confirmed_guests,
        "present_guests": present_guests,
        "pending_guests": confirmed_guests - present_guests,
        "invitations_total": sum(invitation_counts.values()),
        "invitations_pending": invitation_counts["PENDING"],
        "invitations_partial": invitation_counts["PARTIAL"],
        "invitations_complete": invitation_counts["COMPLETE"],
    }
