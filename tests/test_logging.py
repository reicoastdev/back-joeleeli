import json
import logging
import socket

from config.logging import JsonFormatter


def test_json_formatter_ignores_non_http_request_objects():
    record = logging.LogRecord(
        name="django.server",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request completed",
        args=(),
        exc_info=None,
    )
    record.request = socket.socket()

    try:
        payload = json.loads(JsonFormatter().format(record))
    finally:
        record.request.close()

    assert payload["message"] == "request completed"
    assert "method" not in payload
    assert "path" not in payload


def test_json_formatter_redacts_public_invitation_token_from_request_path(rf):
    token = "SUPER_SECRET_PUBLIC_TOKEN_XYZ"
    record = logging.LogRecord(
        name="django.request",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="request completed",
        args=(),
        exc_info=None,
    )
    record.request = rf.get(f"/api/v1/public/invitations/{token}/rsvp/")

    rendered_log = JsonFormatter().format(record)
    payload = json.loads(rendered_log)

    assert token not in rendered_log
    assert payload["path"] == "/api/v1/public/invitations/[REDACTED]/rsvp/"


def test_json_formatter_redacts_public_invitation_token_from_message():
    token = "SUPER_SECRET_PUBLIC_TOKEN_XYZ"
    record = logging.LogRecord(
        name="django.request",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg=f"Not Found: /api/v1/public/invitations/{token}/rsvp/",
        args=(),
        exc_info=None,
    )

    rendered_log = JsonFormatter().format(record)
    payload = json.loads(rendered_log)

    assert token not in rendered_log
    assert payload["message"] == (
        "Not Found: /api/v1/public/invitations/[REDACTED]/rsvp/"
    )
