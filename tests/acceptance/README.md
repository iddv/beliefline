# Acceptance tests

End-to-end checks of Beliefline: 89 file(s), each checking one thing a user, an operator or an attacker could do, through the product's real interface. The helpers in `_helpers/` drive that interface.

Run them from the repository root (they need pytest):

    python -m pytest tests/acceptance

Every test passes on this version.
