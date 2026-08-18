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
