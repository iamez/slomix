"""Compatibility entrypoint for offline team service preparation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.prepare_runtime_consumer_service import (  # noqa: E402
    canonical,  # noqa: F401 -- retained public helper
)
from scripts.prepare_runtime_consumer_service import (
    main as consumer_main,
)
from scripts.prepare_runtime_consumer_service import (
    prepare as prepare_consumer,
)

__all__ = ['canonical', 'prepare', 'main']


def prepare(release, python, environment, destination, expected_commit):
    return prepare_consumer(release, python, environment, destination,
                            expected_commit, component='team')


def main():
    # Append the fixed component so this compatibility command cannot select cache.
    args = sys.argv[1:]
    verifying = any(arg == '--verify-contract' or arg.startswith('--verify-contract=') for arg in args)
    return consumer_main(args if verifying else [*args, '--component', 'team'])


if __name__ == '__main__':
    raise SystemExit(main())
