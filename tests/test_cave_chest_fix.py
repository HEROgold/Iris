"""fix_cave_chest_table writes its hook body into the expansion area, so it must expand the ROM and reserve it."""

from collections.abc import Iterator

import pytest

from constants import CAVE_CHEST_FIX_REGION, EXPANDED_ROM_SIZE, RESERVED_REGIONS
from helpers.files import write_file
from patches.RealCritical import fix_cave_chest_table
from rom_space.pool import pool, reset_pool
from tests.reset_file import reset_file


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    reset_file()
    reset_pool()
    yield
    reset_file()
    reset_pool()


def test_the_rom_is_expanded_to_a_valid_size() -> None:
    fix_cave_chest_table()
    write_file.flush()
    write_file.seek(0, 2)
    assert write_file.tell() == EXPANDED_ROM_SIZE


def test_the_hook_body_is_reserved() -> None:
    assert CAVE_CHEST_FIX_REGION in RESERVED_REGIONS
    fix_cave_chest_table()
    for start, stop in pool().runs():
        assert stop <= CAVE_CHEST_FIX_REGION.start or CAVE_CHEST_FIX_REGION.stop <= start
