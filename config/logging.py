import json
import logging
import re
from datetime import UTC, datetime

SENSITIVE_PUBLIC_INVITATION_PATH = re.compile(
    r"(/api/v1/public/invitations/)[^/?\s]+(?=/|[?\s]|$)"
)


def redact_sensitive_paths(value):
    if not isinstance(value, str):
        return value
    return SENSITIVE_PUBLIC_INVITATION_PATH.sub(r"\1[REDACTED]", value)


class JsonFormatter(logging.Formatter):
    """Render operational logs as one JSON object per line."""

    def format(self, record):
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_sensitive_paths(record.getMessage()),
        }

        status_code = getattr(record, "status_code", None)
        if status_code is not None:
            payload["status_code"] = status_code

        request = getattr(record, "request", None)
        if hasattr(request, "method") and hasattr(request, "path"):
            payload["method"] = request.method
            payload["path"] = redact_sensitive_paths(request.path)

        if record.exc_info:
            payload["exception"] = redact_sensitive_paths(
                self.formatException(record.exc_info)
            )

        return json.dumps(payload, ensure_ascii=False)
