"""Unit tests for the pure pieces behind lead submission: reference numbers, rate limiting,
and the spam heuristics. No database, no HTTP."""

import re

from app.core.ratelimit import RateLimiter
from app.modules.quotes.domain.refs import ALPHABET, new_ref
from app.modules.quotes.domain.spam import screen

REF_PATTERN = re.compile(rf"^TB-[{ALPHABET}]{{6}}$")


def test_a_ref_is_short_prefixed_and_unambiguous() -> None:
    assert REF_PATTERN.match(new_ref())


def test_the_ref_alphabet_avoids_characters_that_get_misheard() -> None:
    """A ref is read down a phone line and typed back into an email."""
    for character in "01OIL2Z5SAEU":
        assert character not in ALPHABET


def test_refs_do_not_repeat_in_practice() -> None:
    assert len({new_ref() for _ in range(500)}) == 500


def test_the_limiter_allows_a_burst_up_to_the_limit() -> None:
    limiter = RateLimiter(limit=3, window_seconds=60)
    assert [limiter.check("a", now=0).allowed for _ in range(4)] == [True, True, True, False]


def test_the_limiter_keys_on_the_caller() -> None:
    limiter = RateLimiter(limit=1, window_seconds=60)
    assert limiter.check("a", now=0).allowed
    assert not limiter.check("a", now=0).allowed
    assert limiter.check("b", now=0).allowed


def test_the_window_slides_rather_than_resetting() -> None:
    limiter = RateLimiter(limit=2, window_seconds=60)
    limiter.check("a", now=0)
    limiter.check("a", now=30)
    assert not limiter.check("a", now=45).allowed
    # The hit at t=0 has aged out by t=61; the one at t=30 has not.
    assert limiter.check("a", now=61).allowed
    assert not limiter.check("a", now=62).allowed


def test_a_rejected_hit_does_not_extend_the_ban() -> None:
    """Hammering a limited endpoint must not keep pushing the window forward, or a client that
    retries in a loop could never recover."""
    limiter = RateLimiter(limit=1, window_seconds=60)
    limiter.check("a", now=0)
    for now in range(1, 60):
        limiter.check("a", now=now)
    assert limiter.check("a", now=61).allowed


def test_a_rejection_says_how_long_to_wait() -> None:
    limiter = RateLimiter(limit=1, window_seconds=60)
    limiter.check("a", now=0)
    assert 0 < limiter.check("a", now=10).retry_after_seconds <= 60


def test_idle_keys_are_forgotten() -> None:
    limiter = RateLimiter(limit=1, window_seconds=60)
    limiter.check("a", now=0)
    limiter.check("b", now=1000)
    assert "a" not in limiter._hits


def test_a_filled_honeypot_reads_as_automated() -> None:
    assert screen(honeypot="http://spam.example", elapsed_ms=9000).automated
    assert screen(honeypot="   ", elapsed_ms=9000).automated is False


def test_a_form_filled_faster_than_a_person_reads_as_automated() -> None:
    assert screen(honeypot="", elapsed_ms=200, min_elapsed_ms=2500).automated
    assert not screen(honeypot="", elapsed_ms=2500, min_elapsed_ms=2500).automated


def test_an_unreported_or_impossible_timing_is_not_held_against_the_submitter() -> None:
    """No timing means JavaScript was off; a negative one means a clock moved. Neither is
    evidence, and neither is worth losing a lead over."""
    assert not screen(honeypot="", elapsed_ms=None).automated
    assert not screen(honeypot="", elapsed_ms=-4000).automated
