from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from website.backend.services.greatshot_store import GreatshotStorageService


@pytest.mark.asyncio
async def test_ensure_schema_skips_ddl_when_schema_ready_and_role_limited():
    service = GreatshotStorageService(project_root=Path("."))
    service._is_schema_ready = AsyncMock(return_value=True)
    service._current_role = AsyncMock(return_value="website_app")
    service._has_schema_ddl_privileges = AsyncMock(return_value=False)
    service._ensure_schema_inner = AsyncMock()

    await service.ensure_schema(db=object())

    service._ensure_schema_inner.assert_not_awaited()


@pytest.mark.asyncio
async def test_ensure_schema_swallows_permission_error_when_schema_not_ready():
    service = GreatshotStorageService(project_root=Path("."))
    service._is_schema_ready = AsyncMock(return_value=False)
    service._current_role = AsyncMock(return_value="website_app")
    service._has_schema_ddl_privileges = AsyncMock(return_value=False)
    service._ensure_schema_inner = AsyncMock(
        side_effect=RuntimeError("must be owner of table greatshot_demos")
    )

    # Should not raise; service logs warning and continues startup.
    await service.ensure_schema(db=object())


@pytest.mark.asyncio
async def test_ensure_schema_raises_non_permission_error():
    service = GreatshotStorageService(project_root=Path("."))
    service._is_schema_ready = AsyncMock(return_value=False)
    service._current_role = AsyncMock(return_value="website_app")
    service._has_schema_ddl_privileges = AsyncMock(return_value=True)
    service._ensure_schema_inner = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(RuntimeError, match="boom"):
        await service.ensure_schema(db=object())
