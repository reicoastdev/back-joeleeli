import hashlib
import json
from uuid import UUID

from django.db import IntegrityError, transaction

from .exceptions import IdempotencyConflict, IdempotencyKeyRequired
from .models import CheckInOperation


def _parse_key(raw_key):
    if not raw_key:
        raise IdempotencyKeyRequired
    try:
        return UUID(raw_key)
    except (TypeError, ValueError, AttributeError):
        raise IdempotencyKeyRequired from None


def _fingerprint(payload):
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


@transaction.atomic
def execute_idempotent(*, event, user, raw_key, action, request_data, operation):
    key = _parse_key(raw_key)
    fingerprint = _fingerprint(request_data)
    stored = (
        CheckInOperation.objects.select_for_update()
        .filter(event=event, user=user, idempotency_key=key)
        .first()
    )
    if stored is None:
        try:
            with transaction.atomic():
                stored = CheckInOperation.objects.create(
                    event=event,
                    user=user,
                    idempotency_key=key,
                    action=action,
                    request_fingerprint=fingerprint,
                )
        except IntegrityError:
            stored = CheckInOperation.objects.select_for_update().get(
                event=event,
                user=user,
                idempotency_key=key,
            )

    if stored.action != action or stored.request_fingerprint != fingerprint:
        raise IdempotencyConflict
    if stored.response_status is not None:
        return stored.response_payload, stored.response_status, True

    response_payload, response_status = operation()
    stored.response_payload = response_payload
    stored.response_status = response_status
    stored.save(update_fields=("response_payload", "response_status"))
    return response_payload, response_status, False
