"""``helpers.relocate.write_relocatable``: rewrite an object in place, or move it to free space."""

from collections.abc import Iterator

import pytest

from helpers.files import write_file
from helpers.relocate import write_relocatable
from tests.reset_file import reset_file


# The zero-filled gap after the shop pointer table in bank $97 (vanilla): free space for these tests.
GAP_START = 0xBEF1D
GAP_END = 0xBF09F
OLD = 0xBDCFE  # Foomy S's record, used as "an object" with a known 83-byte footprint
OLD_SIZE = 83


@pytest.fixture(autouse=True)
def _clean_output() -> Iterator[None]:
    reset_file()
    yield
    reset_file()


def _output() -> bytes:
    write_file.flush()
    write_file.seek(0)
    return write_file.read()


def test_fitting_data_is_written_in_place_and_leftover_zeroed() -> None:
    moved: list[int] = []
    before = _output()
    address = write_relocatable(b"\x11" * 10, OLD, OLD_SIZE, repoint=moved.append, search=(GAP_START, GAP_END))
    after = _output()
    assert address == OLD
    assert moved == []
    assert after[OLD:OLD + 10] == b"\x11" * 10
    assert after[OLD + 10:OLD + OLD_SIZE] == bytes(OLD_SIZE - 10)
    assert after[:OLD] == before[:OLD]
    assert after[OLD + OLD_SIZE:] == before[OLD + OLD_SIZE:]


def test_growing_data_moves_to_free_space_and_zeroes_the_old_bytes() -> None:
    moved: list[int] = []
    data = b"\x22" * (OLD_SIZE + 5)
    before = _output()
    address = write_relocatable(data, OLD, OLD_SIZE, repoint=moved.append, search=(GAP_START, GAP_END))
    after = _output()
    assert moved == [address]
    assert address >= GAP_START
    assert address + len(data) <= GAP_END
    assert before[address:address + len(data)] == bytes(len(data))
    assert after[address:address + len(data)] == data
    assert after[OLD:OLD + OLD_SIZE] == bytes(OLD_SIZE)


def test_relocation_never_covers_avoided_addresses() -> None:
    first_free = GAP_START + 16
    address = write_relocatable(
        b"\x33" * 100, OLD, OLD_SIZE, repoint=lambda _: None, search=(GAP_START, GAP_END), avoid=[first_free],
    )
    assert not address <= first_free < address + 100


def test_no_free_space_raises_and_writes_nothing() -> None:
    before = _output()
    with pytest.raises(ValueError, match="free bytes"):
        write_relocatable(b"\x44" * 500, OLD, OLD_SIZE, repoint=lambda _: None, search=(GAP_START, GAP_END))
    assert _output() == before
