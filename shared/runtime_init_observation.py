"""Bounded InitGame observation vocabulary, NOT identity or authentication.

The trusted source adapter retains the opaque one-shot configure closure. These
public fields cannot recreate it or establish physical-round uniqueness. Host
transport must authenticate the source and separately provision lifecycle epochs.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class InitGameObservation:
    init_time: int
    map_name: str
    round_number: int

    def encode(self):
        if type(self.init_time) is not int or not 0 <= self.init_time <= 2147483647:
            raise ValueError('Invalid observed InitGame time')
        if (not isinstance(self.map_name, str) or '..' in self.map_name
                or re.fullmatch(r'[A-Za-z0-9_.+\-]{1,64}', self.map_name) is None):
            raise ValueError('Invalid observed map')
        if type(self.round_number) is not int or self.round_number not in (1, 2):
            raise ValueError('Invalid observed half')
        return f'slomix_init_v1|{self.init_time}|{self.map_name}|{self.round_number}'


def decode_init_observation(wire: str) -> InitGameObservation:
    if not isinstance(wire, str) or len(wire) > 128:
        raise ValueError('Invalid InitGame observation wire')
    fields = wire.split('|')
    if (len(fields) != 4 or fields[0] != 'slomix_init_v1'
            or re.fullmatch(r'0|[1-9][0-9]{0,9}', fields[1]) is None or fields[3] not in ('1', '2')):
        raise ValueError('Invalid InitGame observation wire')
    value = InitGameObservation(int(fields[1]), fields[2], int(fields[3]))
    if value.encode() != wire:
        raise ValueError('Noncanonical InitGame observation')
    return value
