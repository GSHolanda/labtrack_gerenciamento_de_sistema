import json
import logging

from app.core.logging import JsonFormatter


def test_json_formatter_emits_one_json_object_per_record() -> None:
    record = logging.LogRecord(
        name="labtrack.samples",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Amostra %s recebida",
        args=("SMP-2026-0001",),
        exc_info=None,
    )

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "labtrack.samples"
    assert payload["message"] == "Amostra SMP-2026-0001 recebida"
    assert "timestamp" in payload
