"""Cheap, no-third-party spam heuristics. Pure: no ``fastapi`` or ``sqlmodel`` imports.

Two controls, both aimed at scripted submitters rather than at people:

- **A honeypot field** the form renders but hides. A person never sees it; a bot filling every
  input it can find does.
- **A minimum time-to-submit.** A form filled in under a couple of seconds was not typed.

Neither is security -- a determined submitter can defeat both -- and the failure they must not
have is rejecting a real customer, so both are deliberately generous. The rate limiter is the
control that actually bounds the damage.
"""

from dataclasses import dataclass

DEFAULT_MIN_ELAPSED_MS = 2500


@dataclass(frozen=True)
class SpamVerdict:
    automated: bool
    # Which control fired, for the log. It is never sent to the client: telling a submitter
    # which check it failed is telling it what to change.
    reason: str = ""


def screen(
    honeypot: str,
    elapsed_ms: int | None,
    min_elapsed_ms: int = DEFAULT_MIN_ELAPSED_MS,
) -> SpamVerdict:
    if honeypot.strip():
        return SpamVerdict(automated=True, reason="honeypot")

    # ``None`` means the client never reported a timing (scripts aside, a form submitted with
    # JavaScript disabled cannot). A negative value means a clock moved mid-session. Neither is
    # evidence of anything, and neither is worth losing a lead over.
    if elapsed_ms is not None and 0 <= elapsed_ms < min_elapsed_ms:
        return SpamVerdict(automated=True, reason="too_fast")

    return SpamVerdict(automated=False)
