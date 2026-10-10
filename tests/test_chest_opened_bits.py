"""A red chest's record holds its chest number, the index of its "opened" bit at $7E:093B (Iris-Dev#10)."""

from collections.abc import Iterator

import pytest

from iris.enums.patches import Patch
from iris.helpers.files import read_file
from iris.tables import ChestObject, select, selected


CHEST_TABLE = 0x8B8B5
"""$91:B8B5: a word per map (offset of its entry list), then 3-byte entries ending in $FF."""


@pytest.fixture(autouse=True)
def _vanilla_tables() -> Iterator[None]:
    patch = selected()
    select(Patch.VANILLA)
    yield
    select(patch)


def test_chest_number_is_the_global_index() -> None:
    for index, pointer in enumerate(ChestObject.pointers):
        read_file.seek(pointer)
        misc1, misc2 = read_file.read(2)
        assert misc2 | (misc1 & 0x80) << 1 == index


def test_chest_records_live_in_the_per_map_chest_table() -> None:
    read_file.seek(CHEST_TABLE)
    first_list = int.from_bytes(read_file.read(2), "little")
    assert all(CHEST_TABLE + first_list <= pointer < CHEST_TABLE + 0x1000 for pointer in ChestObject.pointers)
