"""Backward-compatible two-value import failure with an explicit retry signal."""


class RetryableImportFailure(tuple):
    """Unpacks as (False, message); callers must not persist a terminal marker.

    Eligibility for a later poll is not a scheduler or a guarantee of replay
    outside the existing polling/lookback window.
    """

    retryable = True

    def __new__(cls, message: str):
        return super().__new__(cls, (False, message))
