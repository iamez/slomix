"""Exceptional exits retain their identity while releasing owned resources."""

import asyncio
from unittest.mock import Mock

import pytest

from shared.runtime_failure_cleanup import CleanupOnError


class FatalExit(BaseException):
    """An unknown control-flow exception must also trigger resource cleanup."""


@pytest.mark.parametrize('error', [
    OSError('fixture'), KeyboardInterrupt(), SystemExit(3), GeneratorExit(),
    asyncio.CancelledError(), FatalExit(),
    BaseExceptionGroup('fixture', [KeyboardInterrupt()]),
])
def test_exception_is_not_suppressed_or_replaced(error):
    cleanup = Mock()
    with pytest.raises(type(error)) as caught, CleanupOnError(cleanup):
        raise error
    assert caught.value is error
    cleanup.assert_called_once_with()


def test_success_keeps_the_resource_available():
    cleanup = Mock()
    with CleanupOnError(cleanup):
        pass
    cleanup.assert_not_called()


def test_cleanup_failure_retains_original_exception_context():
    original = FatalExit()
    failure = OSError('fixture cleanup failure')
    with pytest.raises(OSError) as caught, CleanupOnError(Mock(side_effect=failure)):
        raise original
    assert caught.value is failure and failure.__context__ is original


def test_success_inside_an_outer_handler_does_not_clean_up():
    cleanup = Mock()
    try:
        raise FatalExit()
    except FatalExit:
        with CleanupOnError(cleanup):
            pass
    cleanup.assert_not_called()
