"""Tests for bot/automation/file_tracker.py module-level helpers.

`calculate_file_hash` and `get_file_size` are the deduplication
foundation — every imported stats file is identified by its SHA256.
A regression in chunked-read or hash algorithm would cause
already-processed files to look "new", causing duplicate imports
and inflated round counts. Pin the contract.
"""
from __future__ import annotations

import hashlib

import pytest

from bot.automation.file_tracker import calculate_file_hash, get_file_size


# ---------------------------------------------------------------------------
# calculate_file_hash
# ---------------------------------------------------------------------------


def test_hash_empty_file_matches_known_sha256(tmp_path):
    """SHA256 of empty bytes is well-known — pin so a future "always
    process headers" change can't silently swap to a different algo."""
    p = tmp_path / "empty.txt"
    p.write_bytes(b"")
    assert calculate_file_hash(str(p)) == hashlib.sha256(b"").hexdigest()


def test_hash_short_content(tmp_path):
    p = tmp_path / "short.txt"
    p.write_bytes(b"hello world")
    expected = hashlib.sha256(b"hello world").hexdigest()
    assert calculate_file_hash(str(p)) == expected


def test_hash_returns_64_char_hex(tmp_path):
    """SHA256 is always 64 chars; rounds_processed table column is
    fixed-width — a regression to MD5 (32) or SHA1 (40) would silently
    truncate or misalign the dedup column."""
    p = tmp_path / "any.txt"
    p.write_bytes(b"some content")
    out = calculate_file_hash(str(p))
    assert len(out) == 64
    assert all(c in "0123456789abcdef" for c in out)


def test_hash_chunked_reads_match_full_file(tmp_path):
    """The implementation reads in 8192-byte chunks. A file >> 8192
    bytes must hash identically to a single hashlib.sha256(full_bytes)."""
    p = tmp_path / "large.bin"
    payload = b"x" * 100_000  # > 12 chunks
    p.write_bytes(payload)
    expected = hashlib.sha256(payload).hexdigest()
    assert calculate_file_hash(str(p)) == expected


def test_hash_at_chunk_boundary_8192_bytes(tmp_path):
    """Exactly one chunk's worth of bytes — boundary case."""
    p = tmp_path / "exact.bin"
    payload = b"y" * 8192
    p.write_bytes(payload)
    expected = hashlib.sha256(payload).hexdigest()
    assert calculate_file_hash(str(p)) == expected


def test_hash_one_byte_more_than_chunk(tmp_path):
    """8193 bytes — forces a partial second chunk read."""
    p = tmp_path / "off-by-one.bin"
    payload = b"z" * 8193
    p.write_bytes(payload)
    expected = hashlib.sha256(payload).hexdigest()
    assert calculate_file_hash(str(p)) == expected


def test_hash_binary_content_with_null_bytes(tmp_path):
    """Stats files are text, but the dedup function shouldn't crash
    on binary input (clip uploads, accidental binary, etc.)."""
    p = tmp_path / "binary.bin"
    payload = bytes(range(256)) * 10  # all 256 byte values
    p.write_bytes(payload)
    expected = hashlib.sha256(payload).hexdigest()
    assert calculate_file_hash(str(p)) == expected


def test_hash_deterministic_across_calls(tmp_path):
    p = tmp_path / "deterministic.txt"
    p.write_bytes(b"same content")
    a = calculate_file_hash(str(p))
    b = calculate_file_hash(str(p))
    c = calculate_file_hash(str(p))
    assert a == b == c


def test_hash_changes_when_content_changes(tmp_path):
    """A single byte flip → completely different hash (avalanche).
    Required for dedup to detect re-uploads of the same filename
    with different content."""
    p = tmp_path / "mutating.txt"
    p.write_bytes(b"version one")
    h1 = calculate_file_hash(str(p))

    p.write_bytes(b"version two")
    h2 = calculate_file_hash(str(p))
    assert h1 != h2


def test_hash_raises_for_missing_file(tmp_path):
    """Caller is responsible for existence check — pin the FileNotFoundError
    behaviour so a future "silently return ''" change is loud."""
    with pytest.raises(FileNotFoundError):
        calculate_file_hash(str(tmp_path / "does-not-exist.txt"))


# ---------------------------------------------------------------------------
# get_file_size
# ---------------------------------------------------------------------------


def test_get_file_size_empty(tmp_path):
    p = tmp_path / "empty.txt"
    p.write_bytes(b"")
    assert get_file_size(str(p)) == 0


def test_get_file_size_known_byte_count(tmp_path):
    p = tmp_path / "12bytes.txt"
    p.write_bytes(b"hello world!")  # 12 bytes
    assert get_file_size(str(p)) == 12


def test_get_file_size_large(tmp_path):
    p = tmp_path / "large.bin"
    p.write_bytes(b"x" * 1_000_000)
    assert get_file_size(str(p)) == 1_000_000


def test_get_file_size_raises_for_missing_file(tmp_path):
    """Same contract as calculate_file_hash — caller checks existence."""
    with pytest.raises(FileNotFoundError):
        get_file_size(str(tmp_path / "does-not-exist.txt"))
