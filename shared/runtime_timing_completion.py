"""Timing-close wire format; parsing alone grants no producer authority.

The host must separately authenticate the peer/process and bind generation and
filename to its accepted dispatch before retaining a receipt or reading bytes.
"""
import re
from dataclasses import dataclass

PREFIX = 'slomix_timing_closed_v1'
MAX_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class TimingCompletion:
    generation: str
    filename: str
    size: int

    def encode(self):
        if not isinstance(self.generation, str) or re.fullmatch('[0-9a-f]{32}', self.generation) is None:
            raise ValueError('Invalid timing completion generation')
        if (not isinstance(self.filename, str) or len(self.filename) > 240
                or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*\.json', self.filename) is None
                or '..' in self.filename):
            raise ValueError('Invalid timing completion filename')
        if type(self.size) is not int or not 1 <= self.size <= MAX_BYTES:
            raise ValueError('Invalid timing completion size')
        return '|'.join((PREFIX, self.generation, self.filename, str(self.size)))


def decode_timing_completion(wire: str) -> TimingCompletion:
    if not isinstance(wire, str) or len(wire) > 512:
        raise ValueError('Invalid timing completion wire')
    fields = wire.split('|')
    if (len(fields) != 4 or fields[0] != PREFIX
            or re.fullmatch('[1-9][0-9]{0,6}', fields[3]) is None):
        raise ValueError('Invalid timing completion wire')
    result = TimingCompletion(fields[1], fields[2], int(fields[3]))
    if result.encode() != wire:
        raise ValueError('Noncanonical timing completion wire')
    return result


@dataclass(frozen=True)
class TimingFilenamePolicy:
    """Trusted map/half expectation when end timestamp is unknown before close.

    This admits a producer-asserted basename; it does not authenticate the suffix
    as a clock or derive physical identity from it. The importer verifies JSON
    against separately trusted round identity and the claimed filename.
    """
    map_name: str
    half: int

    def validate(self):
        if (not isinstance(self.map_name, str)
                or re.fullmatch(r'[A-Za-z0-9_.+-]{1,64}', self.map_name) is None
                or '..' in self.map_name or type(self.half) is not int or self.half not in (1, 2)):
            raise ValueError('Invalid timing filename policy')

    def require(self, filename, dispatch):
        self.validate()
        if (dispatch.map_name != self.map_name or dispatch.identity.round_number != self.half):
            raise ValueError('Timing filename policy disagrees with accepted dispatch')
        sanitized = re.sub(r'[^A-Za-z0-9_-]', '_', self.map_name, flags=re.ASCII)
        if re.fullmatch(r'gametime-' + re.escape(sanitized) + f'-R{self.half}-[1-9][0-9]{{0,18}}\\.json', filename) is None:
            raise ValueError('Timing basename disagrees with provisioned map/half policy')
