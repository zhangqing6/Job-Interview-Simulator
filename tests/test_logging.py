"""JSON Lines logging configuration."""

import json
import logging
from io import StringIO

from interview_simulator.engineering.logging_setup import JsonLinesFormatter, configure_logging


def test_json_lines_formatter_includes_extra_fields() -> None:
    formatter = JsonLinesFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.session_id = "abc"  # type: ignore[attr-defined]
    record.duration_ms = 12.5  # type: ignore[attr-defined]
    line = formatter.format(record)
    payload = json.loads(line)
    assert payload["message"] == "hello"
    assert payload["session_id"] == "abc"
    assert payload["duration_ms"] == 12.5


def test_configure_logging_json_mode() -> None:
    stream = StringIO()
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLinesFormatter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    logging.getLogger("interview_simulator.test").info(
        "probe",
        extra={"request_id": "r1"},
    )
    payload = json.loads(stream.getvalue().strip())
    assert payload["message"] == "probe"
    assert payload["request_id"] == "r1"

    configure_logging(log_format="text", log_level="INFO")
