"""Trusted inline DEV startup verifier, embedded in owner-installed unit text.

Only standard-library code runs before manifest and verifier pins are checked.
The unit and external Python environment are trust anchors; this is integrity
checking under stable trusted ownership, not isolation from a malicious owner.
"""

from base64 import b64encode


BOOTSTRAP_SOURCE = r'''import hashlib, os, stat, sys
from pathlib import Path

def read_regular(path, limit):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError()
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ValueError()
        return raw
    finally:
        os.close(fd)

try:
    root, manifest_pin, verifier_pin, entry = sys.argv[1:5]
    root = Path(root)
    if not root.is_absolute() or root.resolve(strict=True) != root:
        raise ValueError()
    if entry not in ("bot/ultimate_bot.py", "scripts/dev_schema_preflight.py", "web"):
        raise ValueError()
    manifest = read_regular(root / ".slomix-release.json", 4 * 1024 * 1024)
    if hashlib.sha256(manifest).hexdigest() != manifest_pin:
        raise ValueError()
    verifier_path = root / "shared/release_manifest.py"
    if verifier_path.resolve(strict=True) != verifier_path:
        raise ValueError()
    verifier = read_regular(verifier_path, 1024 * 1024)
    if hashlib.sha256(verifier).hexdigest() != verifier_pin:
        raise ValueError()
    scope = {"__name__": "_trusted_release_verifier", "__file__": str(verifier_path)}
    exec(compile(verifier, str(verifier_path), "exec"), scope)
    record = scope["verify_release"](root)
    if entry != "web":
        target = root / entry
        source = read_regular(target, 4 * 1024 * 1024)
        if hashlib.sha256(source).hexdigest() != record["files"][entry]:
            raise ValueError()
except Exception:
    sys.stderr.write('{"status":"refused","reason":"release_startup_integrity"}\n')
    raise SystemExit(1) from None

sys.path.insert(0, str(root))
if entry == "web":
    sys.path.insert(0, str(root / "website"))
    sys.argv = ["uvicorn", *sys.argv[5:]]
    import runpy
    runpy.run_module("uvicorn", run_name="__main__", alter_sys=True)
else:
    sys.argv = [str(target), *sys.argv[5:]]
    exec(compile(source, str(target), "exec"), {
        "__name__": "__main__", "__file__": str(target),
        "_VERIFIED_RELEASE_ROOT": str(root),
    })
'''

# Base64 keeps the inline verifier below systemd 249's 4096-byte argument limit.
# Its alphabet has no whitespace or systemd expansion characters. Only trusted
# stdlib code runs until both external unit pins and the full payload pass.
APP_BOOTSTRAP = ("exec(__import__('base64').b64decode('"
                 + b64encode(BOOTSTRAP_SOURCE.encode()).decode('ascii') + "',validate=True))")
MAX_SYSTEMD_ARGUMENT_BYTES = 4095


def launch_argv(python, release, manifest_pin, verifier_pin, entry, *arguments):
    argv = [str(python), "-I", "-B", "-c", APP_BOOTSTRAP, str(release),
            manifest_pin, verifier_pin, entry, *arguments]
    if any(len(value.encode('utf-8')) > MAX_SYSTEMD_ARGUMENT_BYTES for value in argv):
        raise ValueError('Startup command exceeds the supported systemd argument limit')
    return argv
