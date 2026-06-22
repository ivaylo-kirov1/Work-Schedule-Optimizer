from __future__ import annotations

import secrets

TEMP_PASSWORD_TOKEN_BYTES = 9


def generate_temp_password() -> str:
    return secrets.token_urlsafe(TEMP_PASSWORD_TOKEN_BYTES)
