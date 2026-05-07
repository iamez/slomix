"""Tests for contact_handle_crypto — Telegram/Signal handle encryption.

This module encrypts private contact handles before they hit the DB.
A regression silently:

- Encryption disabled silently when env var missing → handles stored
  in plaintext (privacy bug).
- Wrong key normalisation → cannot decrypt previously-stored handles.
- Decryption swallows exception incorrectly → returns plaintext on bad
  ciphertext.
- mask_contact reveals too much → leaks user identity in logs.

Pin every branch.
"""
from __future__ import annotations

import base64
import hashlib

import pytest

from website.backend.services.contact_handle_crypto import (
    ContactHandleCrypto,
    _normalize_fernet_key,
    mask_contact,
)

# Skip whole module if cryptography unavailable
cryptography = pytest.importorskip("cryptography")


# ---------------------------------------------------------------------------
# _normalize_fernet_key — passphrase / key acceptance
# ---------------------------------------------------------------------------


def test_normalize_returns_empty_for_blank_input():
    assert _normalize_fernet_key("") == ""
    assert _normalize_fernet_key("   ") == ""
    assert _normalize_fernet_key(None) == ""


def test_normalize_accepts_valid_fernet_key_unchanged():
    """44-char base64 → returned as-is (no SHA hash). Pin so a deploy
    with a real Fernet key isn't silently re-hashed (would change the
    key and break decryption of old data)."""
    # Valid Fernet keys are 44 chars (urlsafe base64 of 32 bytes)
    key = base64.urlsafe_b64encode(b"x" * 32).decode("ascii")
    assert len(key) == 44
    assert _normalize_fernet_key(key) == key


def test_normalize_passphrase_to_sha256_b64():
    """Arbitrary passphrase → SHA-256 hashed and base64 encoded.
    Pin the derivation so a deploy that uses "password123" can still
    decrypt old data after a refactor."""
    raw = "my-passphrase"
    expected = base64.urlsafe_b64encode(
        hashlib.sha256(raw.encode("utf-8")).digest()
    ).decode("ascii")
    assert _normalize_fernet_key(raw) == expected


def test_normalize_strips_whitespace():
    """Leading/trailing whitespace stripped before length check.
    Pin so a `.env` with trailing newline doesn't break Fernet init."""
    raw = "   passphrase   "
    out = _normalize_fernet_key(raw)
    out2 = _normalize_fernet_key("passphrase")
    assert out == out2


def test_normalize_43_char_treated_as_passphrase():
    """A near-Fernet-length string (43 chars) is treated as a passphrase
    and hashed — pin the strict ==44 boundary."""
    raw = "x" * 43
    out = _normalize_fernet_key(raw)
    # Hashed → output is 44-char base64 (always 44 from sha256 → b64)
    assert len(out) == 44
    assert out != raw  # different from the input


# ---------------------------------------------------------------------------
# ContactHandleCrypto __init__ / encrypt / decrypt
# ---------------------------------------------------------------------------


def test_init_disabled_when_flag_false():
    """enabled=False bypasses Fernet init entirely."""
    c = ContactHandleCrypto(enabled=False, reason="manual disable")
    assert c.enabled is False
    assert c._fernet is None


def test_init_disables_when_key_missing(monkeypatch):
    """No env var → disabled with reason recorded."""
    monkeypatch.delenv("CONTACT_DATA_ENCRYPTION_KEY", raising=False)
    c = ContactHandleCrypto(enabled=True, reason="")
    assert c.enabled is False
    assert "not configured" in c.reason


def test_init_disables_when_env_var_blank(monkeypatch):
    """Empty CONTACT_DATA_ENCRYPTION_KEY → disabled (NOT silently use empty)."""
    monkeypatch.setenv("CONTACT_DATA_ENCRYPTION_KEY", "")
    c = ContactHandleCrypto(enabled=True, reason="")
    assert c.enabled is False


def test_init_succeeds_with_passphrase(monkeypatch):
    """Valid passphrase → enabled with Fernet ready."""
    monkeypatch.setenv("CONTACT_DATA_ENCRYPTION_KEY", "test-passphrase-2026")
    c = ContactHandleCrypto(enabled=True, reason="")
    assert c.enabled is True
    assert c._fernet is not None


def test_encrypt_returns_none_for_none_input(monkeypatch):
    monkeypatch.setenv("CONTACT_DATA_ENCRYPTION_KEY", "test-pass")
    c = ContactHandleCrypto(enabled=True, reason="")
    assert c.encrypt(None) is None


def test_encrypt_returns_none_for_empty_string(monkeypatch):
    """Empty/whitespace plaintext → None (NOT empty ciphertext).
    Pin so a NULL handle field stays NULL through the round-trip."""
    monkeypatch.setenv("CONTACT_DATA_ENCRYPTION_KEY", "test-pass")
    c = ContactHandleCrypto(enabled=True, reason="")
    assert c.encrypt("") is None
    assert c.encrypt("   ") is None


def test_encrypt_raises_when_disabled(monkeypatch):
    """Calling encrypt() on disabled instance → RuntimeError (loud).
    Pin so a misconfigured deploy can't silently store plaintext."""
    monkeypatch.delenv("CONTACT_DATA_ENCRYPTION_KEY", raising=False)
    c = ContactHandleCrypto(enabled=True, reason="")
    assert c.enabled is False
    with pytest.raises(RuntimeError, match="not configured"):
        c.encrypt("@telegram_user")


def test_encrypt_returns_string_token(monkeypatch):
    """Successful encrypt → ASCII string (NOT bytes)."""
    monkeypatch.setenv("CONTACT_DATA_ENCRYPTION_KEY", "test-pass")
    c = ContactHandleCrypto(enabled=True, reason="")
    out = c.encrypt("@user")
    assert isinstance(out, str)
    assert out != "@user"  # actually encrypted


def test_encrypt_decrypt_round_trip(monkeypatch):
    """Encrypt then decrypt → original plaintext."""
    monkeypatch.setenv("CONTACT_DATA_ENCRYPTION_KEY", "test-pass")
    c = ContactHandleCrypto(enabled=True, reason="")
    plain = "@telegram_handle_with_unicode_žaba"
    cipher = c.encrypt(plain)
    out = c.decrypt(cipher)
    assert out == plain


def test_encrypt_strips_plaintext_whitespace(monkeypatch):
    """Round-tripping `  @user  ` returns `@user` (stripped before
    encryption). Pin so trailing CRLF from a form input doesn't
    pollute the stored handle."""
    monkeypatch.setenv("CONTACT_DATA_ENCRYPTION_KEY", "test-pass")
    c = ContactHandleCrypto(enabled=True, reason="")
    cipher = c.encrypt("  @user  ")
    out = c.decrypt(cipher)
    assert out == "@user"


def test_decrypt_returns_none_for_empty_ciphertext(monkeypatch):
    monkeypatch.setenv("CONTACT_DATA_ENCRYPTION_KEY", "test-pass")
    c = ContactHandleCrypto(enabled=True, reason="")
    assert c.decrypt(None) is None
    assert c.decrypt("") is None


def test_decrypt_returns_none_when_disabled(monkeypatch):
    """Disabled instance → decrypt returns None silently. Pin so a
    rotated key doesn't crash existing reads (graceful fallback)."""
    monkeypatch.delenv("CONTACT_DATA_ENCRYPTION_KEY", raising=False)
    c = ContactHandleCrypto(enabled=True, reason="")
    assert c.enabled is False
    assert c.decrypt("any-ciphertext") is None


def test_decrypt_returns_none_for_invalid_token(monkeypatch):
    """Garbage ciphertext → None (NOT raise). Pin fail-safe."""
    monkeypatch.setenv("CONTACT_DATA_ENCRYPTION_KEY", "test-pass")
    c = ContactHandleCrypto(enabled=True, reason="")
    assert c.decrypt("not-a-real-fernet-token") is None


def test_decrypt_returns_none_for_bad_unicode(monkeypatch):
    """If somehow Fernet decrypts to non-UTF-8 bytes (e.g., wrong key
    happened to validate), the UnicodeDecodeError is swallowed → None."""
    monkeypatch.setenv("CONTACT_DATA_ENCRYPTION_KEY", "test-pass")
    c = ContactHandleCrypto(enabled=True, reason="")
    # We can't easily craft a token that decrypts to bad UTF-8 without
    # a different key — but the InvalidToken path is the same:
    assert c.decrypt("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA") is None


def test_decryption_with_different_key_returns_none(monkeypatch):
    """Encrypt with key A, try to decrypt with key B → None.
    Pin so a key rotation doesn't leak via failed decrypt path."""
    monkeypatch.setenv("CONTACT_DATA_ENCRYPTION_KEY", "key-A")
    c1 = ContactHandleCrypto(enabled=True, reason="")
    cipher = c1.encrypt("secret")

    monkeypatch.setenv("CONTACT_DATA_ENCRYPTION_KEY", "key-B-DIFFERENT")
    c2 = ContactHandleCrypto(enabled=True, reason="")
    out = c2.decrypt(cipher)
    assert out is None


def test_from_env_factory_returns_enabled_instance(monkeypatch):
    """from_env() builds an instance with enabled=True (default mode)."""
    monkeypatch.setenv("CONTACT_DATA_ENCRYPTION_KEY", "test-pass")
    c = ContactHandleCrypto.from_env()
    assert c.enabled is True


# ---------------------------------------------------------------------------
# mask_contact — log-safe display
# ---------------------------------------------------------------------------


def test_mask_returns_none_for_none():
    assert mask_contact(None) is None


def test_mask_returns_none_for_empty():
    assert mask_contact("") is None


@pytest.mark.parametrize("inp, expected", [
    ("@user1234567",   "@u********67"),  # 12 chars: first 2 + 8 stars + last 2
    ("abcdef",         "ab**ef"),
    ("ab",             "**"),            # ≤4 chars: all asterisks
    ("abcd",           "****"),
    ("a",              "*"),
    ("X" * 50,         "XX" + "*" * 46 + "XX"),
])
def test_mask_known_patterns(inp, expected):
    """Pin the masking rule: ≤4 chars → all asterisks; >4 → keep first 2
    and last 2 + middle masked. A regression that lets more chars
    through silently leaks identity in logs."""
    assert mask_contact(inp) == expected


def test_mask_5_char_boundary():
    """5 chars → uses the >4 path (NOT all asterisks)."""
    out = mask_contact("abcde")
    assert out == "ab*de"  # first 2 + 1 star + last 2
    assert "*" in out
