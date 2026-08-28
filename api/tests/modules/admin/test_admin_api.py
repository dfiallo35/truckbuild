"""The admin endpoints, run against the seeded Postgres database (migrate, seed, then run this
suite -- same setup as tests/test_catalog_api.py).

The one these exist for: **the token is the only thing standing between a stranger and every
customer's name, email, and phone number.** Every route under /v1/admin is checked for that here,
by walking the app's own route table rather than by a list someone has to remember to extend.
"""

import itertools

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.infrastructure.ratelimit import RateLimiter
from app.main import app
from app.modules.quotes.dependencies import get_rate_limiter

client = TestClient(app)
settings = get_settings()

AUTH = {"Authorization": f"Bearer {settings.admin_token}"}

DEFAULT_SELECTION = [
    "cab-regular",
    "shell-standard",
    "galley-compact",
    "suspension-standard",
    "finish-satin-black",
]

_ips = itertools.count(1)


@pytest.fixture(autouse=True)
def _fresh_limiter():
    """A limiter of this test's own -- this suite submits real leads to build its fixtures, and
    the real limiter is process-global. See tests/modules/quotes/test_quotes_api.py."""
    app.dependency_overrides[get_rate_limiter] = lambda: RateLimiter(
        limit=settings.quote_rate_limit,
        window_seconds=settings.quote_rate_limit_window_seconds,
    )
    yield
    app.dependency_overrides.pop(get_rate_limiter, None)


def submit(**overrides) -> dict:
    """A real lead, submitted the way the site submits one, so the admin list is reading rows
    the public endpoint wrote rather than rows this test invented."""
    payload = {
        "platform_slug": "bristlecone",
        "option_slugs": [*DEFAULT_SELECTION, "bumper-heavy", "winch-12000"],
        "contact": {"name": "Dana Reyes", "email": "dana@example.com", "phone": "+1 555 0100"},
        "intended_use": "Two-up desert travel.",
        "timeline": "3–6 months",
        "notes": "Prefers the satin finish.",
        "website": "",
        "elapsed_ms": 9_000,
    }
    payload.update(overrides)
    ip = f"198.51.100.{next(_ips) % 250 + 1}"
    response = client.post("/v1/quotes", json=payload, headers={"x-forwarded-for": ip})
    assert response.status_code == 201, response.text
    return response.json()


def admin_paths() -> list[tuple[str, str]]:
    """Every admin route the app actually serves, as (method, path-with-a-plausible-value).

    Read from the OpenAPI document rather than walking ``app.routes``, whose shape is FastAPI's
    own business -- what matters is that a route added under /v1/admin tomorrow is checked for
    the token by this suite without anyone remembering to add it here.
    """
    routes = [
        (method.upper(), path.replace("{ref}", "TB-NOPE00"))
        for path, operations in app.openapi()["paths"].items()
        if path.startswith("/v1/admin")
        for method in operations
        if method.upper() not in {"HEAD", "OPTIONS"}
    ]
    assert routes, "no admin routes found -- has the router moved?"
    return routes


@pytest.mark.parametrize(("method", "path"), admin_paths())
def test_every_admin_route_refuses_an_anonymous_caller(method: str, path: str) -> None:
    response = client.request(method, path, json={})
    assert response.status_code == 401, f"{method} {path} answered {response.status_code}"
    assert response.json()["code"] == "unauthorized"
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(("method", "path"), admin_paths())
def test_every_admin_route_refuses_the_wrong_token(method: str, path: str) -> None:
    wrong = {"Authorization": f"Bearer {settings.admin_token}x"}
    response = client.request(method, path, json={}, headers=wrong)
    assert response.status_code == 401, f"{method} {path} answered {response.status_code}"


def test_a_submitted_build_is_readable_in_the_list() -> None:
    quote = submit()

    response = client.get("/v1/admin/quotes", headers=AUTH)
    assert response.status_code == 200, response.text

    body = response.json()
    row = next(item for item in body["items"] if item["ref"] == quote["ref"])
    assert row["contact_name"] == "Dana Reyes"
    assert row["contact_email"] == "dana@example.com"
    assert row["platform_slug"] == "bristlecone"
    assert row["total_cents"] == quote["total_cents"]
    assert row["line_count"] == len(quote["lines"])
    assert body["total"] >= len(body["items"])


def test_the_list_is_newest_first() -> None:
    older = submit(notes="older")
    newer = submit(notes="newer")

    refs = [item["ref"] for item in client.get("/v1/admin/quotes", headers=AUTH).json()["items"]]
    assert refs.index(newer["ref"]) < refs.index(older["ref"])


def test_the_list_pages_without_dropping_or_repeating_a_lead() -> None:
    for _ in range(3):
        submit()

    first = client.get("/v1/admin/quotes?limit=2&offset=0", headers=AUTH).json()
    second = client.get("/v1/admin/quotes?limit=2&offset=2", headers=AUTH).json()

    assert len(first["items"]) == 2
    assert first["total"] == second["total"] >= 3
    assert not {item["ref"] for item in first["items"]} & {item["ref"] for item in second["items"]}


def test_the_list_pages_of_one_do_not_drop_or_repeat_a_lead() -> None:
    """The ``id`` tiebreak exists for exactly this: three leads can land inside one test with the
    same ``created_at`` down to the microsecond, and a page boundary that wobbles on that would
    drop or repeat one."""
    submitted = {submit()["ref"] for _ in range(3)}

    total = client.get("/v1/admin/quotes?limit=1&offset=0", headers=AUTH).json()["total"]
    seen = [
        client.get(f"/v1/admin/quotes?limit=1&offset={offset}", headers=AUTH).json()["items"][0][
            "ref"
        ]
        for offset in range(total)
    ]
    assert len(seen) == len(set(seen)), "a page of one repeated a lead"
    assert submitted <= set(seen)


def test_the_list_filters_by_kind() -> None:
    submit()
    response = client.get("/v1/admin/quotes?kind=enquiry", headers=AUTH)
    assert response.status_code == 200
    assert all(item["kind"] == "enquiry" for item in response.json()["items"])


def test_the_list_filters_by_platform() -> None:
    submit()
    response = client.get("/v1/admin/quotes?platform_slug=ironwood", headers=AUTH)
    assert all(item["platform_slug"] == "ironwood" for item in response.json()["items"])


def test_the_list_searches_by_reference_and_by_person() -> None:
    quote = submit(contact={"name": "Wren Okafor", "email": "wren@example.com", "phone": ""})

    by_ref = client.get(f"/v1/admin/quotes?q={quote['ref']}", headers=AUTH).json()
    assert [item["ref"] for item in by_ref["items"]] == [quote["ref"]]
    assert by_ref["total"] == 1

    by_name = client.get("/v1/admin/quotes?q=okafor", headers=AUTH).json()
    assert quote["ref"] in {item["ref"] for item in by_name["items"]}


def test_a_search_wildcard_is_a_literal_not_a_pattern() -> None:
    """``%`` means percent to the person typing it into a search box."""
    submit()
    assert client.get("/v1/admin/quotes?q=%25", headers=AUTH).json()["total"] == 0


def test_the_detail_endpoint_carries_the_whole_lead() -> None:
    quote = submit()

    response = client.get(f"/v1/admin/quotes/{quote['ref']}", headers=AUTH)
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["contact"] == {
        "name": "Dana Reyes",
        "email": "dana@example.com",
        "phone": "+1 555 0100",
    }
    assert body["notes"] == "Prefers the satin finish."
    assert body["intended_use"] == "Two-up desert travel."
    assert body["timeline"] == "3–6 months"
    assert body["total_cents"] == quote["total_cents"]
    assert [line["option_slug"] for line in body["lines"]] == [
        line["option_slug"] for line in quote["lines"]
    ]


def test_an_unknown_reference_is_a_404_in_the_api_error_shape() -> None:
    response = client.get("/v1/admin/quotes/TB-NOPE00", headers=AUTH)
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_an_enquiry_reads_back_with_no_build() -> None:
    response = client.post(
        "/v1/enquiries",
        json={
            "contact": {"name": "Sam Vale", "email": "sam@example.com", "phone": ""},
            "intended_use": "",
            "timeline": "",
            "notes": "Just asking.",
            "website": "",
            "elapsed_ms": 9_000,
        },
        headers={"x-forwarded-for": "198.51.100.251"},
    )
    assert response.status_code == 201, response.text
    ref = response.json()["ref"]

    body = client.get(f"/v1/admin/quotes/{ref}", headers=AUTH).json()
    assert body["kind"] == "enquiry"
    assert body["total_cents"] is None
    assert body["lines"] == []
