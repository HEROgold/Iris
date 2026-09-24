"""The byte-equality helper every ``test_writing_*`` test relies on must actually detect a changed byte."""

import pytest

from helpers.files import original_file, write_file
from tests.reset_file import test_equal as files_equal


def _flip(address: int) -> None:
    write_file.seek(address)
    byte = original_file.read_bytes()[address]
    write_file.write(bytes([byte ^ 0xFF]))


def test_equal_detects_unflushed_write() -> None:
    _flip(0xBDD29)
    with pytest.raises(AssertionError):
        files_equal()


def test_equal_detects_write_after_earlier_call() -> None:
    files_equal()
    _flip(0xBDD29)
    with pytest.raises(AssertionError):
        files_equal()


def test_equal_resets_the_file_after_a_mismatch() -> None:
    _flip(0xBDD29)
    with pytest.raises(AssertionError):
        files_equal()
    files_equal()
