"""Every vanilla locked door needs a key item, and the keys open the doors of their own dungeons."""

from collections.abc import Iterator

import pytest

from iris.enums.patches import Patch
from iris.structures.key_doors import key_doors
from iris.tables import select, selected

KEY_ITEMS = range(423, 467)


@pytest.fixture(autouse=True)
def _vanilla_tables() -> Iterator[None]:
    patch = selected()
    select(Patch.VANILLA)
    yield
    select(patch)


def test_vanilla_has_23_key_doors() -> None:
    doors = key_doors()
    assert len(doors) == 23
    assert all(door.item in KEY_ITEMS for door in doors)


def test_known_doors() -> None:
    doors = {(door.map_index, door.item) for door in key_doors()}
    assert (0x06, 429) in doors  # Door key, Cave to Sundletan B1
    assert (0x0C, 432) in doors  # Lake key, Lake Cave B3
    assert (0x3C, 434) in doors  # Wind key, Gordovan West Tower 5F
