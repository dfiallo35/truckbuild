"""Quote reference numbers. Pure: no ``fastapi`` or ``sqlmodel`` imports.

A ref is read aloud over the phone and typed back into an email, so the alphabet drops every
character that gets confused when spoken or handwritten (0/O, 1/I/L, 2/Z, 5/S) and every vowel,
which keeps randomly generated refs from spelling words at anyone.
"""

import secrets

ALPHABET = "BCDFGHJKMNPQRTVWXY346789"
REF_LENGTH = 6
REF_PREFIX = "TB"


def new_ref() -> str:
    """A short, unambiguous public identifier such as ``TB-K7MQ4C``.

    ~1.9e8 possibilities: collisions are rare but not impossible, which is why the caller
    retries against the unique index on ``quote.ref`` rather than assuming uniqueness here.
    """
    body = "".join(secrets.choice(ALPHABET) for _ in range(REF_LENGTH))
    return f"{REF_PREFIX}-{body}"
