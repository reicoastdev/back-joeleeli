import json
import logging
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    """Render operational logs as one JSON object per line."""

    def format(self, record):
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        status_code = getattr(record, "status_code", None)
        if status_code is not None:
            payload["status_code"] = status_code

        request = getattr(record, "request", None)
        if hasattr(request, "method") and hasattr(request, "path"):
            payload["method"] = request.method
            payload["path"] = request.path

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)
