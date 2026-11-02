"""Read explicit proximity declarations without inventing canonical DB links."""

import re
from collections.abc import Iterable
from pathlib import Path

from shared.runtime_round_identity import RoundIdentity, decode_round_identity


def proximity_header_identity(lines: Iterable[str], filename: str) -> RoundIdentity | None:
    """Legacy files remain unbound; present declarations require exact headers.

    Caller bounds the input. Scan all comments so a second declaration cannot be
    hidden after a data section. This checks agreement, not source authenticity.
    """
    counts = {'map': 0, 'round': 0, 'runtime_identity': 0}
    values = {}
    for raw in lines:
        line = raw.strip()
        for key in counts:
            prefix = '# ' + key + '='
            if line.startswith(prefix):
                counts[key] += 1
                values[key] = line[len(prefix):]
            elif key == 'runtime_identity' and line.startswith('# runtime_identity'):
                raise ValueError('Malformed proximity runtime declaration')
    if counts['runtime_identity'] == 0:
        return None
    if any(count != 1 for count in counts.values()):
        raise ValueError('Proximity identity requires unique map/round/declaration headers')
    identity = decode_round_identity(values['runtime_identity'])
    name = re.fullmatch(r'\d{4}-\d{2}-\d{2}-\d{6}-([A-Za-z0-9_.+-]{1,64})-round-([12])_engagements\.txt',
                        Path(filename).name, re.ASCII)
    if (name is None or name.group(1) != values['map']
            or name.group(2) != values['round']
            or values['round'] != str(identity.round_number)):
        raise ValueError('Proximity filename/header/declared identity conflict')
    return identity
