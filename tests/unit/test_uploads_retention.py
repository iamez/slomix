"""Upload retention (migration 070) and admin delete.

Two things the library never had: a retention choice at upload time, and a way
for an admin to take down someone else's file. These tests pin the parts that
are easy to get subtly wrong — the meaning of "lifetime", who may delete, and
the fact that expiry is enforced on READ rather than only by the sweep.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.routers import uploads as U


def _req(user_id: int | None = 7, csrf: bool = True):
    r = MagicMock()
    r.headers = {"x-requested-with": "XMLHttpRequest"} if csrf else {}
    r.session = {"user": {"id": user_id, "username": "x"}} if user_id is not None else {}
    return r


# ---------------------------------------------------------------------------
# Retention values
# ---------------------------------------------------------------------------

def test_lifetime_is_null_not_a_large_number():
    """"Forever" must not be spelled as "expires in N years".

    A sentinel date would silently become a deletion the day it arrives, years
    after everyone stopped thinking about it.
    """
    assert None not in U._RETENTION_DAYS
    assert U._RETENTION_DAYS == {7, 30, 90}


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [1, 14, 365, 0, -7])
async def test_unlisted_retention_is_rejected(bad):
    with pytest.raises(HTTPException) as e:
        await U.upload_file(_req(), file=MagicMock(), retention_days=bad, db=AsyncMock())
    assert e.value.status_code == 400
    assert "retention_days" in str(e.value.detail)


@pytest.mark.asyncio
async def test_retention_is_validated_before_the_file_is_touched():
    """A bad value must not leave a stored file behind.

    Validation sits above _get_storage(), so a rejected upload never reaches
    the disk — asserted by the storage helper never being called.
    """
    with patch.object(U, "_get_storage") as storage:
        with pytest.raises(HTTPException):
            await U.upload_file(_req(), file=MagicMock(), retention_days=999, db=AsyncMock())
    storage.assert_not_called()


# ---------------------------------------------------------------------------
# Expiry is enforced on read, not only by the sweep
# ---------------------------------------------------------------------------

def test_live_clause_covers_both_halves():
    """Active AND unexpired. Either half alone is a bug:

    status only -> lapsed uploads stay listed until someone runs the sweep;
    expiry only -> deleted uploads come back.
    """
    assert "status = 'active'" in U._LIVE
    assert "expires_at IS NULL" in U._LIVE
    assert "expires_at > CURRENT_TIMESTAMP" in U._LIVE


def test_live_clause_has_a_qualified_twin_for_joins():
    """The tag and list queries alias uploads as u, so they need u.-prefixed
    columns. Both spellings must express the same rule."""
    assert U._LIVE_U == "u.status = 'active' AND (u.expires_at IS NULL OR u.expires_at > CURRENT_TIMESTAMP)"


# ---------------------------------------------------------------------------
# Who may delete
# ---------------------------------------------------------------------------

def test_uploader_may_delete_their_own():
    with patch.object(U, "_configured_admin_ids", return_value=set()):
        assert U._may_delete(_req(user_id=7), 7) is True


def test_stranger_may_not_delete():
    with patch.object(U, "_configured_admin_ids", return_value=set()):
        assert U._may_delete(_req(user_id=8), 7) is False


def test_admin_may_delete_someone_elses():
    with patch.object(U, "_configured_admin_ids", return_value={99}):
        assert U._may_delete(_req(user_id=99), 7) is True


def test_anonymous_may_not_delete():
    with patch.object(U, "_configured_admin_ids", return_value={99}):
        assert U._may_delete(_req(user_id=None), 7) is False


def test_unparseable_session_id_may_not_delete():
    """A malformed session must fail closed, not raise."""
    with patch.object(U, "_configured_admin_ids", return_value={99}):
        assert U._may_delete(_req(user_id="not-a-number"), 7) is False


# ---------------------------------------------------------------------------
# Sweep
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sweep_requires_admin():
    db = AsyncMock()
    with patch.object(U, "require_admin_user", side_effect=HTTPException(status_code=403)):
        with pytest.raises(HTTPException) as e:
            await U.sweep_expired_uploads(_req(user_id=7), db=db)
    assert e.value.status_code == 403
    db.fetch_all.assert_not_awaited()


@pytest.mark.asyncio
async def test_sweep_unlinks_before_marking_deleted():
    """Order matters, and it is the opposite of what looks safer.

    Marking first would leave a failed unlink behind a row the next sweep can
    never select again — the sweep looks for status = 'active' — so the file
    would sit on disk forever with nothing tracking it.
    """
    db = AsyncMock()
    db.fetch_all.return_value = [("abc", "/data/abc.cfg")]
    calls: list[str] = []
    db.execute.side_effect = lambda *a, **k: calls.append("db")
    storage = MagicMock()
    storage.delete_upload.side_effect = lambda *a: calls.append("file")

    with patch.object(U, "require_admin_user", return_value={"id": 99}), \
         patch.object(U, "_get_storage", return_value=storage):
        out = await U.sweep_expired_uploads(_req(user_id=99), db=db)

    assert calls == ["file", "db"]
    assert out == {"success": True, "swept": 1, "file_errors": 0}


@pytest.mark.asyncio
async def test_a_failed_unlink_stays_eligible_for_the_next_sweep():
    """The row whose file could not be removed must stay active, so a later
    sweep retries it. It is not visible meanwhile: _LIVE hides expired rows
    from every read, so it is invisible AND retryable.

    One unreadable path must also not strand the rest of the batch.
    """
    db = AsyncMock()
    db.fetch_all.return_value = [("a", "/x/a"), ("b", "/x/b"), ("c", "/x/c")]
    storage = MagicMock()
    storage.delete_upload.side_effect = [OSError("gone"), None, None]

    with patch.object(U, "require_admin_user", return_value={"id": 99}), \
         patch.object(U, "_get_storage", return_value=storage):
        out = await U.sweep_expired_uploads(_req(user_id=99), db=db)

    # Two swept, not three: "a" keeps its row so the next sweep can try again.
    assert out == {"success": True, "swept": 2, "file_errors": 1}

    # Assert WHICH rows were updated, not just how many. A count of 2 would also
    # pass if the sweep had marked "a" deleted and skipped "b" or "c" — the exact
    # inversion of the contract this test exists to protect (CodeRabbit on #615).
    updated = [call.args[1][0] for call in db.execute.await_args_list]
    assert updated == ["b", "c"], f"expected only b and c to be marked deleted, got {updated}"


@pytest.mark.asyncio
async def test_sweep_with_nothing_to_do_touches_no_storage():
    db = AsyncMock()
    db.fetch_all.return_value = []
    with patch.object(U, "require_admin_user", return_value={"id": 99}), \
         patch.object(U, "_get_storage") as storage:
        out = await U.sweep_expired_uploads(_req(user_id=99), db=db)
    assert out == {"success": True, "swept": 0, "file_errors": 0}
    storage.assert_not_called()


# ---------------------------------------------------------------------------
# The form fields must be Form(), not bare defaults
# ---------------------------------------------------------------------------

def test_upload_text_fields_are_declared_as_form_parameters():
    """A plain scalar default on a POST is a QUERY parameter to FastAPI, while
    the upload form sends multipart/form-data — so such a field silently never
    arrives, with no error anywhere.

    This is not hypothetical. Before the fix, the dev database held 5 uploads:
    0 with a title different from the filename, 0 with a description, and
    upload_tags was empty. The Title / Description / Tags inputs had never done
    anything, and retention_days was about to inherit the same fate.
    """
    import inspect
    from fastapi.params import Form as FormParam

    sig = inspect.signature(U.upload_file)
    for name in ("title", "description", "tags", "category", "retention_days"):
        default = sig.parameters[name].default
        assert isinstance(default, FormParam), (
            f"{name} must be declared as Form(...); a bare default makes it a "
            f"query parameter and the multipart form field is dropped silently"
        )
