"""Error types for demo scanning."""


class DemoScanError(Exception):
    """Base scanner failure."""


class UnsupportedDemoError(DemoScanError):
    """Unsupported format or protocol."""


class ParseToolMissingError(DemoScanError):
    """Required external parser binary is not available."""


class ParseToolFailedError(DemoScanError):
    """External parser failed or timed out."""
