"""Renaming a zone: the compressed name lands on the zone's own bytes and nowhere else (HER-244).

Names are decoded here with an independent reader that follows terrorwave's ``parse_name``: ``0A lo hi`` is a
little-endian word, length ``(word >> 12) + 2``, copied from ``0x38000 + (word & 0xFFF)``.
"""

from collections.abc import Iterator

import pytest

from helpers.files import original_file, output_bytes
from helpers.name import compress_name
from structures.zone import Zone
from tests.reset_file import reset_file


NAME_WINDOW = 0x38000
FIRST_NAME = 0x38810
CAVE = 5  # "Secret Skills Cave", 19 bytes
ELCID = 3  # "Elcid", 6 bytes, before the cave's name


@pytest.fixture(autouse=True)
def _clean_output() -> Iterator[None]:
    reset_file()
    yield
    reset_file()
    for index in (CAVE, ELCID):  # Zone objects are cached for the whole session; forget the test's rename
        zone = Zone.from_index(index)
        zone._modified_name = None  # noqa: SLF001
        zone._name = None  # noqa: SLF001


def _decode(rom: bytes, pointer: int) -> bytes:
    name = bytearray()
    while rom[pointer] != 0x00:
        if rom[pointer] == 0x0A:
            word = int.from_bytes(rom[pointer + 1:pointer + 3], "little")
            source = NAME_WINDOW + (word & 0xFFF)
            name += rom[source:source + (word >> 12) + 2]
            pointer += 3
        else:
            name.append(rom[pointer])
            pointer += 1
    return bytes(name)


def _name_starts(rom: bytes, count: int) -> list[int]:
    """Where each of the first ``count`` packed names starts, walking terminator to terminator."""
    starts, pointer = [], FIRST_NAME
    for _ in range(count):
        starts.append(pointer)
        pointer = rom.index(b"\x00", pointer) + 1
    return starts


def test_a_rename_writes_only_the_zones_own_bytes() -> None:
    before = original_file.read_bytes()
    zone = Zone.from_index(CAVE)
    start, end = zone.start, zone.end
    zone.name = "Elcid Cave"
    zone.write()
    after = output_bytes()

    assert after[:start] == before[:start]  # includes offset 0, where the old code wrote
    assert after[end:] == before[end:]
    assert _decode(after, start).rstrip(b" ") == b"Elcid Cave"
    assert _name_starts(after, 40) == _name_starts(before, 40)  # later zones keep their names and indices


def test_a_rename_back_references_an_earlier_name() -> None:
    zone = Zone.from_index(CAVE)
    zone.name = "Elcid Cave"
    zone.write()
    elcid = Zone.from_index(ELCID).start
    word = (5 - 2) << 12 | (elcid - NAME_WINDOW)  # "Elcid", 5 bytes
    assert output_bytes()[zone.start:zone.start + 8] == b"\x0a" + word.to_bytes(2, "little") + b" Cave"


def test_a_name_that_does_not_fit_raises_and_writes_nothing() -> None:
    zone = Zone.from_index(ELCID)
    zone.name = "Elcid Kingdom"
    with pytest.raises(ValueError, match="only 6 are free"):
        zone.write()
    assert output_bytes() == original_file.read_bytes()


def test_compress_name_writes_nothing() -> None:
    compress_name(Zone.from_index(CAVE).start, b"Elcid Cave")
    assert output_bytes() == original_file.read_bytes()
