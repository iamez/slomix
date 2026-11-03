"""Bind a live controller handoff to explicitly authorized bounded CLI options."""
from copy import copy

from bot.runtime_timing_import_cli import execute, validate_arguments
from shared.runtime_captured_timing_match import CapturedTimingMatch


def bind_captured_timing_arguments(options, captured):
    """Replace source references only; never invent database/handover authority.

    Caller supplies parsed CLI options and explicit writer handover confirmations.
    No credentials, target configuration or activation flags derive from payloads.
    """
    if not isinstance(captured, CapturedTimingMatch):
        raise ValueError('Successful captured timing match required')
    captured.verify()
    args = copy(options)
    args.spool = str(captured.stats.first.root)
    args.timing_directory = str(captured.timings[0].root)
    args.timing_generation_directories = True
    args.expected_round_identities = (captured.stats.first_identity, captured.stats.second_identity)
    for half, stats, timing in zip((1, 2), (captured.stats.first, captured.stats.second),
                                   captured.timings, strict=True):
        ref = stats.reference
        setattr(args, f'r{half}', (ref.generation, ref.filename, str(ref.size), ref.sha256))
        setattr(args, f'timing_r{half}', (timing.generation, timing.filename,
                                        str(timing.size), timing.sha256))
    validate_arguments(args)
    return args


async def import_captured_timing_match(options, captured, progress):
    """Run existing CLI engine in its owning process/event loop.

    execute owns SIGTERM handling; this is an explicit one-shot host entrypoint,
    not an arbitrary background coroutine inside the bot/web event loop.
    """
    return await execute(bind_captured_timing_arguments(options, captured), progress)
