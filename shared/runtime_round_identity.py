"""Opt-in v1 producer identity vocabulary; agreement is NOT authentication.

Default-off: stats, timing and proximity writers emit it only after explicit
runtime binding. A trusted producer authority must allocate non-reused IDs and
distribute them across modules/restarts before establishing physical identity.
IDs name a match and physical half, not a timestamp, artifact generation or DB ID.
"""

import re
from dataclasses import dataclass

PREFIX = 'slomix_round_v1'


@dataclass(frozen=True)
class RoundIdentity:
    source_id: str
    match_id: str
    round_id: str
    round_number: int
    first_round_id: str

    def __post_init__(self):
        if (not isinstance(self.source_id, str)
                or re.fullmatch(r'[a-z0-9][a-z0-9_.-]{0,63}', self.source_id, re.ASCII) is None):
            raise ValueError('Invalid identity source')
        for token in (self.match_id, self.round_id, self.first_round_id):
            if not isinstance(token, str) or re.fullmatch(r'[0-9a-f]{32}', token, re.ASCII) is None:
                raise ValueError('Invalid identity token')
        if type(self.round_number) is not int or self.round_number not in (1, 2):
            raise ValueError('Identity requires half 1 or 2')
        if (self.round_id == self.first_round_id) != (self.round_number == 1):
            raise ValueError('Identity has invalid first-half dependency')

    def encode(self):
        return ':'.join((PREFIX, self.source_id, self.match_id, self.round_id,
                         str(self.round_number), self.first_round_id))


def decode_round_identity(value: str) -> RoundIdentity:
    """Strict bounded wire parsing; absent/unknown versions are not identities."""
    if not isinstance(value, str) or len(value) > 200:
        raise ValueError('Invalid identity wire value')
    fields = value.split(':')
    if len(fields) != 6 or fields[0] != PREFIX or fields[4] not in ('1', '2'):
        raise ValueError('Unsupported or malformed round identity')
    return RoundIdentity(fields[1], fields[2], fields[3], int(fields[4]), fields[5])


def stats_header_identity(header: str) -> RoundIdentity | None:
    """Read a proposed optional tenth c0rn field without guessing legacy identity.

    Not a complete stats-header validator. Eight/nine fields have no identity. Extra
    or malformed extension fields fail, never degrade to legacy. Used only by
    opt-in validation: no DB writes, source authentication, uniqueness or lifecycle
    continuity are implied, and the legacy statistics calculations are unchanged.
    """
    if not isinstance(header, str) or len(header) > 4096:
        raise ValueError('Invalid identity header')
    line = header.removesuffix('\n')
    if header.endswith('\n'):
        line = line.removesuffix('\r')
    if '\n' in line or '\r' in line:
        raise ValueError('Expected one stats header line')
    fields = line.split('\\')
    if len(fields) in (8, 9):
        return None
    if len(fields) != 10:
        raise ValueError('Unsupported identity header shape')
    identity = decode_round_identity(fields[9])
    if fields[3] != str(identity.round_number):
        raise ValueError('Stats header and identity half disagree')
    return identity


def require_round_pair(first: RoundIdentity, second: RoundIdentity) -> None:
    """Check declared R1->R2 agreement; never certify actual physical provenance.

    Caller authenticates records AND their immutable artifact bindings. Successful
    comparison is insufficient for canonical DB linking or historical backfill.
    """
    if not isinstance(first, RoundIdentity) or not isinstance(second, RoundIdentity):
        raise ValueError('Explicit round identities required')
    if (first.round_number != 1 or second.round_number != 2
            or first.source_id != second.source_id or first.match_id != second.match_id
            or first.round_id != second.first_round_id):
        raise ValueError('Declared round pair disagrees')
