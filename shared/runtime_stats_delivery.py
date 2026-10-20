"""Bounded host ticket serialization for explicitly provisioned Lua IPC peers.

Epochs come from the trusted host lifecycle authority, never a clock or VM slot.
This serializer neither allocates epochs nor authenticates a running game process.
Provision the exact same expectations privately at sender and receiver; do not
use a received message to choose its own expected epoch, peer or source.
"""

import re
from dataclasses import dataclass

from shared.runtime_round_identity import RoundIdentity, decode_round_identity
from shared.runtime_stats_dispatch import StatsDispatch

PREFIX = 'slomix_stats_bind_v1'
ACK_PREFIX = 'slomix_stats_ack_v1'


@dataclass(frozen=True)
class StatsDelivery:
    process_epoch: str
    lifecycle_epoch: str
    init_time: int
    dispatch: StatsDispatch

    def encode(self):
        if not isinstance(self.dispatch, StatsDispatch) or not isinstance(self.dispatch.identity, RoundIdentity):
            raise ValueError('Explicit stats dispatch required')
        for token in (self.process_epoch, self.lifecycle_epoch, self.dispatch.generation):
            if not isinstance(token, str) or re.fullmatch('[0-9a-f]{32}', token) is None:
                raise ValueError('Invalid delivery token')
        if self.process_epoch == self.lifecycle_epoch:
            raise ValueError('Process and lifecycle epochs must be distinct')
        artifact_tokens = {self.dispatch.generation, self.dispatch.identity.match_id,
                           self.dispatch.identity.round_id, self.dispatch.identity.first_round_id}
        if self.process_epoch in artifact_tokens or self.lifecycle_epoch in artifact_tokens:
            raise ValueError('Epochs must be distinct from round/artifact identities')
        if type(self.init_time) is not int or not 0 <= self.init_time <= 2147483647:
            raise ValueError('Invalid InitGame levelTime')
        name = self.dispatch.map_name
        if (not isinstance(name, str) or re.fullmatch(r'[A-Za-z0-9_.+\-]{1,64}', name) is None
                or '..' in name):
            raise ValueError('Invalid delivery map')
        return '|'.join((PREFIX, self.process_epoch, self.lifecycle_epoch, str(self.init_time),
                         self.dispatch.identity.encode(), self.dispatch.generation, name))

    def acknowledgement(self):
        return self.encode().replace(PREFIX, ACK_PREFIX, 1)


def decode_stats_delivery(wire: str) -> StatsDelivery:
    if not isinstance(wire, str) or len(wire) > 512:
        raise ValueError('Invalid delivery wire')
    fields = wire.split('|')
    if (len(fields) != 7 or fields[0] != PREFIX
            or re.fullmatch(r'0|[1-9][0-9]{0,9}', fields[3]) is None):
        raise ValueError('Invalid delivery wire')
    delivery = StatsDelivery(fields[1], fields[2], int(fields[3]),
                             StatsDispatch(decode_round_identity(fields[4]), fields[5], fields[6]))
    if delivery.encode() != wire:
        raise ValueError('Noncanonical delivery wire')
    return delivery
