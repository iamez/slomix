"""Public Discord links, independent of the internal website API address."""

from urllib.parse import quote, urlsplit


def validate_ui_mode(value: str) -> str:
    if value not in ("legacy", "app"):
        raise ValueError("WEBSITE_UI_MODE must be legacy or app")
    return value


def website_url(config, route: str) -> str:
    """Build an explicit legacy hash URL or a new SPA deep link.

    The base is an origin, not /app or an API URL. Never infer the UI from
    the environment name: existing deployments retain legacy links by default.
    Routes are application-owned paths, not arbitrary external destinations.
    """
    mode = validate_ui_mode(getattr(config, "website_ui_mode", "legacy"))
    base = getattr(config, "website_public_base", "https://www.slomix.fyi")
    parsed = urlsplit(base)
    if (
        parsed.scheme not in ("http", "https") or not parsed.hostname
        or parsed.username is not None or parsed.password is not None
        or parsed.path not in ("", "/") or parsed.query or parsed.fragment
        or any(char.isspace() or ord(char) < 32 for char in base)
        or "\\" in base
    ):
        raise ValueError("WEBSITE_PUBLIC_BASE must be an HTTP(S) origin without credentials")
    # Accessing port also rejects malformed/out-of-range ports.
    _ = parsed.port
    if (
        not route.startswith("/") or route.startswith("//")
        or any(part in (".", "..") for part in route.split("/"))
        or any(ord(char) < 32 for char in route) or "\\" in route
    ):
        raise ValueError("Website route must be a local absolute path")
    path = quote(route, safe="/-._~")
    return f"{base.rstrip('/')}{'/app' if mode == 'app' else '/#'}{path}"
