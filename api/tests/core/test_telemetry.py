"""Telemetry: request ids, structured logs, and the scrubbing that keeps leads out of Sentry.

The scrubber is the part worth testing hardest. It is the only thing standing between a
customer's name, email and phone number and a third-party error tracker, and a mistake in it
is invisible until it has already shipped the data.
"""

import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.telemetry import REQUEST_ID_HEADER, _scrub
from app.core.telemetry import install as install_telemetry
from app.main import app

client = TestClient(app)


def test_every_response_carries_a_request_id() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER]


def test_a_caller_supplied_request_id_is_kept() -> None:
    """A trace started in the web app keeps its identity across the hop into this service."""
    response = client.get("/healthz", headers={REQUEST_ID_HEADER: "abc123"})
    assert response.headers[REQUEST_ID_HEADER] == "abc123"


def test_request_ids_differ_between_requests() -> None:
    first = client.get("/healthz").headers[REQUEST_ID_HEADER]
    second = client.get("/healthz").headers[REQUEST_ID_HEADER]
    assert first != second


def test_requests_are_logged_as_json_with_the_routed_template(caplog) -> None:
    """A slug-bearing path is the case that matters: the log must group by endpoint rather
    than opening a fresh bucket for every platform anyone ever looks at."""
    with caplog.at_level(logging.INFO, logger="app.telemetry"):
        client.get("/v1/platforms/bristlecone")

    lines = [json.loads(record.message) for record in caplog.records]
    entry = next(line for line in lines if line["event"] == "request")
    assert entry["method"] == "GET"
    assert entry["route"] == "/v1/platforms/{slug}"
    assert entry["path"] == "/v1/platforms/bristlecone"
    assert isinstance(entry["duration_ms"], float)
    assert entry["request_id"]


def test_an_unrouted_path_falls_back_to_the_raw_path(caplog) -> None:
    """A 404 has no route to template, and must still produce a usable line."""
    with caplog.at_level(logging.INFO, logger="app.telemetry"):
        client.get("/no-such-endpoint")

    lines = [json.loads(record.message) for record in caplog.records]
    entry = next(line for line in lines if line["event"] == "request")
    assert entry["route"] == "/no-such-endpoint"
    assert entry["status"] == 404


def test_the_health_check_is_not_logged(caplog) -> None:
    """The platform polls it every few seconds; logging that says nothing."""
    with caplog.at_level(logging.INFO, logger="app.telemetry"):
        client.get("/healthz")

    events = [json.loads(record.message)["event"] for record in caplog.records]
    assert "request" not in events


def test_an_unhandled_exception_is_logged_with_its_request_id(caplog) -> None:
    """The failure must reach stdout with its id even when Sentry is off -- which is the
    configuration everywhere except production. Built on its own app because the real one has
    no route that raises, and adding one to it would expose a crash endpoint in production."""
    crashing = FastAPI()
    install_telemetry(crashing, get_settings())

    @crashing.get("/boom")
    async def boom() -> None:
        raise RuntimeError("kaboom")

    with caplog.at_level(logging.ERROR, logger="app.telemetry"), pytest.raises(RuntimeError):
        TestClient(crashing).get("/boom", headers={REQUEST_ID_HEADER: "trace-me"})

    entry = json.loads(caplog.records[-1].message)
    assert entry["event"] == "request.failed"
    assert entry["request_id"] == "trace-me"
    assert entry["path"] == "/boom"


def test_scrub_drops_the_request_body() -> None:
    """A quote body holds a name, an email and a phone number."""
    event = _scrub(
        {
            "request": {
                "data": {"contact": {"email": "buyer@example.com", "phone": "555-0100"}},
                "cookies": {"session": "secret"},
                "url": "https://api.example.com/v1/quotes",
            }
        },
        {},
    )

    assert event is not None
    assert "data" not in event["request"]
    assert "cookies" not in event["request"]
    # The non-sensitive context survives -- scrubbing everything would make reports useless.
    assert event["request"]["url"] == "https://api.example.com/v1/quotes"


def test_scrub_redacts_credential_headers_case_insensitively() -> None:
    event = _scrub(
        {
            "request": {
                "headers": {
                    "Authorization": "Bearer supersecret",
                    "cookie": "session=secret",
                    "User-Agent": "Mozilla/5.0",
                }
            }
        },
        {},
    )

    assert event is not None
    headers = event["request"]["headers"]
    assert headers["Authorization"] == "[redacted]"
    assert headers["cookie"] == "[redacted]"
    assert headers["User-Agent"] == "Mozilla/5.0"


def test_scrub_tolerates_an_event_with_no_request() -> None:
    """Not every Sentry event comes from a request; a crash in the seed has no request at all."""
    assert _scrub({"level": "error"}, {}) == {"level": "error"}
