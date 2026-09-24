import json
from decimal import Decimal

import httpx
import pytest

from simulator.client import ApiError, LabTrackClient


def _client(handler) -> LabTrackClient:  # type: ignore[no-untyped-def]
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return LabTrackClient("http://lab/api/v1/", "lt_inst_secret", http=http)


def test_requests_carry_the_key_and_exact_decimal() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(201, json={"status": "ACCEPTED"})

    client = _client(handler)
    client.submit_result("PH-METER-01", "SMP-2026-0001", "PH", Decimal("7.10"), "pH")
    client.worklist(limit=5)
    client.heartbeat("PH-METER-01")

    submit, worklist, heartbeat = seen
    assert all(r.headers["X-Instrument-Key"] == "lt_inst_secret" for r in seen)
    assert str(submit.url) == "http://lab/api/v1/instruments/results"
    assert json.loads(submit.content) == {
        "instrument_id": "PH-METER-01",
        "sample_code": "SMP-2026-0001",
        "test": "PH",
        "result": "7.10",
        "unit": "pH",
    }
    assert str(worklist.url) == "http://lab/api/v1/instruments/worklist?limit=5"
    assert json.loads(heartbeat.content) == {"instrument_id": "PH-METER-01"}


def test_error_envelope_becomes_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = {
            "error": {
                "code": "UNIT_MISMATCH",
                "message": "Unidade diferente",
                "details": {"message_id": 42},
                "request_id": "x",
            }
        }
        return httpx.Response(422, json=body)

    with pytest.raises(ApiError) as exc:
        _client(handler).submit_result("PH", "SMP", "PH", Decimal(7), "mV")
    assert (exc.value.status_code, exc.value.code, exc.value.message_id) == (
        422,
        "UNIT_MISMATCH",
        42,
    )


def test_non_json_error_and_connection_failure() -> None:
    with pytest.raises(ApiError) as exc:
        _client(lambda _: httpx.Response(502, text="Bad gateway")).worklist()
    assert exc.value.code == "HTTP_502"
    assert exc.value.message_id is None

    def offline(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("recusada", request=request)

    with pytest.raises(ApiError) as exc:
        _client(offline).heartbeat("PH-METER-01")
    assert (exc.value.status_code, exc.value.code) == (0, "CONNECTION_ERROR")
