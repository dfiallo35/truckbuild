"""The cache revalidation webhook, from this side.

Two contracts. **It never raises** -- a catalog load that succeeded must not be reported as a
failure because a cache could not be reached. And **it never fails quietly** -- a revalidation
that did not happen leaves a wrong price on a public page, so every failure is logged at ERROR
and the result says so.
"""

import logging

import httpx
import pytest

from app.core.config import Settings
from app.core.revalidate import revalidate, tags_for_platforms


@pytest.fixture
def settings() -> Settings:
    return Settings(web_base_url="https://truckbuild.example/", revalidate_secret="s3cret")


@pytest.fixture
def calls(monkeypatch) -> list[dict]:
    """Capture the request instead of sending it, answering 200 unless a test says otherwise."""
    recorded: list[dict] = []

    def fake_post(url, *, json, headers, timeout):
        recorded.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    return recorded


def test_the_tags_go_to_the_web_app_with_the_shared_secret(settings, calls) -> None:
    result = revalidate(["catalog", "platform-bristlecone"], settings)

    assert result.ok
    assert len(calls) == 1
    assert calls[0]["url"] == "https://truckbuild.example/api/revalidate"
    assert calls[0]["json"] == {"tags": ["catalog", "platform-bristlecone"]}
    assert calls[0]["headers"]["Authorization"] == "Bearer s3cret"


def test_a_repeated_tag_is_sent_once(settings, calls) -> None:
    result = revalidate(["catalog", "catalog", "platform-ironwood"], settings)
    assert calls[0]["json"] == {"tags": ["catalog", "platform-ironwood"]}
    assert result.tags == ("catalog", "platform-ironwood")


def test_no_tags_means_no_request(settings, calls) -> None:
    assert revalidate([], settings).ok
    assert calls == []


def test_a_rejected_secret_is_reported_and_explained(settings, monkeypatch, caplog) -> None:
    def fake_post(url, **_):
        return httpx.Response(401, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    with caplog.at_level(logging.ERROR):
        result = revalidate(["catalog"], settings)

    assert not result.ok
    assert "401" in result.detail
    # The failure mode this hint exists for: two REVALIDATE_SECRET values drifting apart, whose
    # only other symptom is a public page quietly showing last week's price.
    assert "REVALIDATE_SECRET" in result.detail
    assert "cache revalidation failed" in caplog.text


def test_an_unreachable_web_app_fails_loudly_without_raising(settings, monkeypatch, caplog) -> None:
    def fake_post(url, **_):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", fake_post)

    with caplog.at_level(logging.ERROR):
        result = revalidate(["catalog"], settings)

    assert not result.ok
    assert "https://truckbuild.example/api/revalidate" in result.detail
    assert caplog.records and caplog.records[0].levelno == logging.ERROR


def test_a_platform_change_takes_the_catalog_tag_with_it() -> None:
    """A repriced option changes the platform page *and* the "from $X" on every listing."""
    assert tags_for_platforms(["bristlecone", "ironwood"]) == [
        "catalog",
        "platform-bristlecone",
        "platform-ironwood",
    ]


def test_the_same_platform_named_twice_yields_one_tag() -> None:
    assert tags_for_platforms(["ironwood", "ironwood"]) == ["catalog", "platform-ironwood"]
