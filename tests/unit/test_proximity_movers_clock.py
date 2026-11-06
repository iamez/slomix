"""Actual HTTP contract with a stub DB; native SQL proof lives in integration."""

import httpx
import pytest
from fastapi import FastAPI

from website.backend.dependencies import get_db
from website.backend.routers.proximity_movement import router


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['empty', 'rows', 'error'])
async def test_raw_quality_is_explicit_in_every_response(mode):
    class Adapter:
        async def fetch_all(self, sql, params=()):
            if mode == 'error':
                raise RuntimeError('synthetic database failure')
            return [] if mode == 'empty' else [('G1', 'Synthetic', 100, 1)]

    app = FastAPI()
    app.include_router(router, prefix='/api')
    app.dependency_overrides[get_db] = Adapter
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get('/api/proximity/movers?session_date=2099-01-01')
    assert response.status_code == 200  # intentional error-body convention
    body = response.json()
    assert body['status'] == {'empty': 'prototype', 'rows': 'ok', 'error': 'error'}[mode]
    quality = body['elapsed_time_quality']
    assert quality['basis'] == 'raw_source_timestamps'
    assert quality['active_time_verified'] is False
    assert 'pauses' in quality['reason']
    assert 'zero end sentinel' in quality['survival_excludes']
    assert 'first move after a known end' in quality['reaction_excludes']
    if mode == 'error':
        assert body['ready'] is False
        assert body['reaction'] == body['survival'] == []
