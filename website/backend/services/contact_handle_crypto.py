"""Encryption helpers for private contact handles (Telegram/Signal)."""

from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass

try:
    from cryptography.fernet import Fernet, InvalidToken
except Exception:  # pragma: no cover - optional dependency guard
    Fernet = None  # type: ignore[assignment]
    InvalidToken = Exception  # type: ignore[assignment]


def _normalize_fernet_key(raw_key: str) -> str:
    value = (raw_key or "").strip()
    if not value:
        return ""

    # Accept either a valid Fernet key or an arbitrary passphrase.
    if len(value) == 44:
        return value

    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii")


@dataclass
class ContactHandleCrypto:
    enabled: bool
    reason: str

    def __post_init__(self) -> None:
        self._fernet = None
        if not self.enabled:
            return
        if Fernet is None:
            self.enabled = False
            self.reason = "cryptography package is not installed"
            return

        key = _normalize_fernet_key(os.getenv("CONTACT_DATA_ENCRYPTION_KEY", ""))
        if not key:
            self.enabled = False
            self.reason = "CONTACT_DATA_ENCRYPTION_KEY is not configured"
            return

        self._fernet = Fernet(key.encode("ascii"))

    @classmethod
    def from_env(cls) -> "ContactHandleCrypto":
        return cls(enabled=True, reason="")

    def encrypt(self, plaintext: str | None) -> str | None:
        if plaintext is None:
            return None
        value = str(plaintext).strip()
        if not value:
            return None
        if not self.enabled or self._fernet is None:
            raise RuntimeError(self.reason or "encryption is not available")
        token = self._fernet.encrypt(value.encode("utf-8"))
        return token.decode("ascii")

    def decrypt(self, ciphertext: str | None) -> str | None:
        if not ciphertext:
            return None
        if not self.enabled or self._fernet is None:
            return None
        try:
            value = self._fernet.decrypt(ciphertext.encode("ascii"))
            return value.decode("utf-8")
        except (InvalidToken, ValueError, UnicodeDecodeError):
            return None


def mask_contact(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value)
    if len(text) <= 4:
        return "*" * len(text)
    return f"{text[:2]}{'*' * (len(text) - 4)}{text[-2:]}"
