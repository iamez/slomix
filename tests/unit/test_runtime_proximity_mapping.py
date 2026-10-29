"""Declared linkage contracts: independent authority, parent evidence and safe scope."""

import hashlib
from dataclasses import replace
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from shared.runtime_proximity_mapping import (
    ROUND_TABLES,
    DeclaredMappingPending,
    DeclaredProximityBinding,
    ResolvedDeclaredParent,
    reject_existing_children,
    resolve_declared_parent,
    validate_declared_receipt,
)
from tests.unit.test_runtime_round_identity import FIRST, SECOND

DAY = date(2026, 10, 8)
NAME = '2026-10-08-120000-supply-round-1_engagements.txt'


def source():
    payload = f'# map=supply\n# round=1\n# runtime_identity={FIRST.encode()}\n'.encode()
    binding = DeclaredProximityBinding(FIRST.source_id, 'd' * 32, NAME, len(payload),
                                       hashlib.sha256(payload).hexdigest(), DAY)
    return payload, binding


@pytest.mark.parametrize('map_name', ['sw_goldrush_te', 'supply', 'map.pk3', 'map+variant', 'map-name'])
def test_declared_proximity_accepts_transport_map_alphabet(map_name):
    payload = f'# map={map_name}\n# round=1\n# runtime_identity={FIRST.encode()}\n'.encode()
    filename = f'2026-10-08-120000-{map_name}-round-1_engagements.txt'
    binding = DeclaredProximityBinding(FIRST.source_id, 'd' * 32, filename, len(payload),
                                       hashlib.sha256(payload).hexdigest(), DAY)
    assert binding.verify(payload, filename, DAY) == (FIRST, map_name)


@pytest.mark.parametrize('changes', [
    {'source_id': 'Uppercase'}, {'source_id': ''}, {'generation': 'D' * 32}, {'filename': '../bad.txt'},
    {'size': True}, {'size': 0}, {'size': 8388609}, {'sha256': None}, {'sha256': 'A' * 64},
    {'session_date': '2026-10-08'},
])
def test_invalid_binding_rejected(changes):
    _, binding = source()
    with pytest.raises(ValueError):
        replace(binding, **changes)


@pytest.mark.parametrize('kind', ['bytes', 'digest', 'filename', 'date', 'source', 'missing_header'])
def test_trusted_binding_is_not_learned_from_payload(kind):
    payload, binding = source()
    name, day = NAME, DAY
    if kind == 'bytes':
        payload += b'\n'
    elif kind == 'digest':
        binding = replace(binding, sha256='0' * 64)
    elif kind == 'filename':
        name = NAME.replace('120000', '120001')
    elif kind == 'date':
        day = date(2026, 10, 9)
    elif kind == 'source':
        binding = replace(binding, source_id='other')
    else:
        payload = b'# map=supply\n# round=1\n'
        binding = replace(binding, size=len(payload), sha256=hashlib.sha256(payload).hexdigest())
    with pytest.raises(ValueError):
        binding.verify(payload, name, day)


def reader():
    identities = (FIRST, SECOND)
    maps, parents, events = {}, {}, {}
    for half, identity in enumerate(identities, 1):
        filename = f'2026-09-25-120000-supply-round-{half}.txt'
        maps[identity.round_id] = [identity.source_id, identity.round_id, identity.match_id, half,
                                  identity.first_round_id, 'supply', filename, half, 'a' * 64]
        parents[half] = ['supply', half, 20, '2026-09-25-120000', '2026-09-25', '120000']
        events[half] = [filename, 'a' * 64, True, half, 20]

    async def fetch(query, params=()):
        if 'FROM runtime_round_mappings' in query:
            return maps.get(params[1])
        if 'FROM rounds' in query:
            return parents.get(params[0])
        if 'FROM runtime_events' in query:
            return events.get(params[0])
        raise AssertionError(query)

    return SimpleNamespace(fetch_one=AsyncMock(side_effect=fetch)), maps, parents, events


@pytest.mark.parametrize('lock', [True, False])
async def test_exact_parent_checks_both_halves_and_explicit_lock_policy(lock):
    adapter, *_ = reader()
    assert await resolve_declared_parent(adapter, SECOND, 'supply', lock=lock) == ResolvedDeclaredParent(2, 20)
    assert adapter.fetch_one.await_count == 6
    assert all(('FOR SHARE' in call.args[0]) is lock for call in adapter.fetch_one.await_args_list)


@pytest.mark.parametrize('kind', ['missing_mapping', 'missing_first', 'map', 'match', 'first', 'half',
    'filename', 'parent_map', 'parent_session', 'parent_match', 'parent_date', 'parent_time',
    'missing_event', 'event_digest', 'event_validation', 'first_event'])
async def test_mapping_parent_and_journal_contradictions_fail_closed(kind):
    adapter, maps, parents, events = reader()
    if kind == 'missing_mapping':
        maps.pop(SECOND.round_id)
    elif kind == 'missing_first':
        maps.pop(FIRST.round_id)
    elif kind in ('map', 'match', 'first', 'half', 'filename'):
        index = {'map': 5, 'match': 2, 'first': 4, 'half': 3, 'filename': 6}[kind]
        maps[SECOND.round_id][index] = 'wrong'
    elif kind.startswith('parent_'):
        index = {'parent_map': 0, 'parent_session': 2, 'parent_match': 3, 'parent_date': 4, 'parent_time': 5}[kind]
        parents[2][index] = None if kind == 'parent_session' else 'wrong'
    elif kind == 'missing_event':
        events.pop(2)
    elif kind == 'first_event':
        events[1][2] = False
    else:
        events[2][1 if kind == 'event_digest' else 2] = False
    with pytest.raises(DeclaredMappingPending if kind.startswith('missing_') and kind != 'missing_event' else ValueError):
        await resolve_declared_parent(adapter, SECOND, 'supply')


@pytest.mark.parametrize('table', ROUND_TABLES)
async def test_every_round_child_collision_blocks(table):
    async def exists(query, params):
        return (f'FROM {table} WHERE' in query,)
    adapter = SimpleNamespace(fetch_one=AsyncMock(side_effect=exists))
    with pytest.raises(ValueError, match='child scope'):
        await reject_existing_children(adapter, ResolvedDeclaredParent(10, 20),
                                        {'round_num': 1, 'round_start_unix': 0}, DAY)
    query, params = adapter.fetch_one.await_args.args
    special = table in ('proximity_revive', 'proximity_weapon_accuracy')
    assert ('session_date=?' not in query) is special
    assert params[-1] == (None if special else 0)


@pytest.mark.parametrize('kind', ['receipt_absent', 'proof_absent', 'legacy_flag', 'wrong_parent',
                                 'wrong_source', 'wrong_generation', 'wrong_size', 'wrong_date'])
async def test_receipt_proof_must_be_exact(kind):
    _, binding = source()
    parent = ResolvedDeclaredParent(10, 20)
    receipt = [binding.sha256, True, True, 10]
    proof = [binding.source_id, binding.generation, FIRST.round_id, binding.size, binding.sha256, DAY, 10]
    if kind == 'receipt_absent':
        receipt = None
    elif kind == 'proof_absent':
        proof = None
    elif kind == 'legacy_flag':
        receipt[1] = False
    elif kind == 'wrong_parent':
        receipt[3] = 11
    else:
        proof[{'wrong_source': 0, 'wrong_generation': 1, 'wrong_size': 3, 'wrong_date': 5}[kind]] = 'wrong'
    adapter = SimpleNamespace(fetch_one=AsyncMock(side_effect=[receipt, proof]))
    with pytest.raises(ValueError, match='provenance'):
        await validate_declared_receipt(adapter, binding, FIRST, parent)
