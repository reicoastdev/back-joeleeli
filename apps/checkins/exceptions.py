from rest_framework.exceptions import APIException


class IdempotencyKeyRequired(APIException):
    status_code = 400
    default_detail = "A valid Idempotency-Key UUID header is required."
    default_code = "idempotency_key_required"


class IdempotencyConflict(APIException):
    status_code = 409
    default_detail = "This Idempotency-Key was already used for another request."
    default_code = "idempotency_conflict"
