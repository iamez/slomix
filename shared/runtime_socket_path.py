"""Lexical contract shared by offline game assembly and the local listener.

No filesystem access: future socket parents need not exist during preparation.
The listener separately checks canonical existing, private, same-UID placement.
"""

import re
from pathlib import PurePosixPath


def validate_socket_path(value: str) -> None:
    if (not isinstance(value, str) or re.fullmatch(r'/[A-Za-z0-9_./-]+', value) is None
            or len(value) > 107 or value.startswith('//')
            or '..' in PurePosixPath(value).parts
            or PurePosixPath(value).as_posix() != value
            or re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', PurePosixPath(value).name) is None):
        raise ValueError('Explicit canonical bounded ASCII Unix socket pathname required')
