"""Print a verified ET2.85 rehearsal startup recipe; never execute it.

The owner-approved supervisor must supply private stdin, drain stdout/stderr,
pin the resulting process, and only then attach the listener/map-release hook.
This recipe is not a service, a network sandbox, or permission to start one.
"""

import argparse
import json
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.prepare_runtime_bot_fixture import verify as verify_bots  # noqa: E402
from scripts.prepare_runtime_game_workspace import verify  # noqa: E402


def startup_recipe(directory: Path, *, port=27962, idle_seconds=300,
                   bot_fixture=None, bot_manifest_sha256=None):
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError('Explicit unprivileged UDP port required')
    if type(idle_seconds) is not int or not 30 <= idle_seconds <= 600:
        raise ValueError('Idle watchdog must be between 30 and 600 seconds')
    record = verify(directory)
    if (bot_fixture is None) != (bot_manifest_sha256 is None):
        raise ValueError('Bot fixture and manifest pin must be supplied together')
    if bot_fixture is not None:
        if bot_fixture.is_relative_to(directory) or directory.is_relative_to(bot_fixture):
            raise ValueError('Bot fixture must be separate from game workspace')
        verify_bots(bot_fixture, bot_manifest_sha256)
    # ET reconstructs argv as console text, not a shell. Literal double quotes
    # retain empty values; a Python empty string alone disappears in that text.
    settings = {
        'fs_basepath': record['fs_basepath'], 'fs_homepath': record['fs_homepath'],
        'fs_game': 'legacy', 'fs_basegame': '', 'dedicated': '1',
        'net_ip': '127.0.0.1', 'net_enabled': '1', 'net_port': str(port),
        'sv_advert': '0', 'sv_allowDownload': '0', 'sv_wwwDownload': '0',
        'rconPassword': '', 'g_luaModuleList': '', 'lua_allowedModules': '',
        'lua_modules': 'slomix_runtime_entry.lua', 'g_gametype': '3',
        # ET2.85 defaults to defaultpublic; G_configSet can reload settings and
        # queue an extra map_restart during G_InitGame. Empty explicitly opts out.
        'g_customConfig': '', 'omnibot_enable': '0', 'g_nextTimeLimit': '0',
        'g_currentRound': '0', 'nextmap': '', 'nextcampaign': '',
        'com_watchdog': str(idle_seconds), 'com_watchdog_cmd': 'quit',
    }
    if bot_fixture is not None:
        settings.update({'omnibot_enable': '1', 'omnibot_path': str(bot_fixture),
                         'g_doWarmup': '0', 'g_warmup': '10', 'sv_maxclients': '12'})
    argv = [record['executable']]
    for name, value in settings.items():
        argv.extend(('+set', name, value if value else '""'))
    # Sys_BuildCommandLine -> char commandLine[MAX_STRING_CHARS] (1024).
    # Paths are canonical ASCII without spaces, validated by workspace.verify.
    wire = ''.join(arg + ' ' for arg in argv[1:])
    if len(wire.encode('ascii')) >= 1024 or len(settings) >= 32:
        raise ValueError('ET startup exceeds its 1024-byte or 32-console-line buffer')
    return {
        'status': 'startup_recipe_only', 'activation_ready': False,
        'workspace': record, 'argv': argv, 'cwd': record['fs_homepath'],
        'env': {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C', 'HOME': record['fs_homepath']},
        'settings': settings, 'console_release': 'map supply\n',
        'requires': ['owner-approved systemctl supervisor', 'private exclusive stdin pipe',
                     'continuous bounded stdout/stderr drain', 'approved live process pin',
                     'listener ready before console release', 'real engine configuration proof'],
        'round_fixture': {
            'players': 'six_bots_requested_not_observed' if bot_fixture else 'not_provisioned',
            'bots': 'verified_fixture_requested' if bot_fixture else 'disabled',
            'transition': 'ET2.85 SV_SpawnServer sets nextmap=map_restart 0',
            'completion': 'natural stopwatch exit; no forced timer or fabricated result',
            'shutdown': 'supervisor exit and systemd cleanup after both captures',
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--port', type=int, default=27962)
    parser.add_argument('--idle-seconds', type=int, default=300)
    parser.add_argument('--bot-fixture', type=Path)
    parser.add_argument('--bot-manifest-sha256')
    args = parser.parse_args(argv)
    try:
        print(json.dumps(startup_recipe(args.directory, port=args.port,
                                        idle_seconds=args.idle_seconds, bot_fixture=args.bot_fixture,
                                        bot_manifest_sha256=args.bot_manifest_sha256), sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        print(json.dumps({'status': 'refused', 'error_type': type(exc).__name__,
                          'activation_ready': False}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
