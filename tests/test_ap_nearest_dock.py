"""A Ship item before the Treadool scene appears at the dock nearest the player (Iris-Dev#67).

key_items.asm's ShipState writes ``NearestDock[$05AC]`` to the pending dock ``$09EE`` instead of 7D(01)'s Treadool
dock. docks.py builds that table from the ROM's exits and the world map's dock section. Static checks on the table and
on the committed base patches (``tools/build_ap_basepatch.py --check`` keeps them current);
``tests/emulator/ship_dock.lua`` checks it in the game.
"""

import pytest
from iris.constants import RX_CODE_REGION
from iris.helpers import files
from iris.helpers.addresses import address_from_lorom
from iris.patches.archipelago.overworld.docks import (
    FIRST_TOWN_DOCK,
    TABLE_SIZE,
    TREADOOL_DOCK,
    nearest_dock,
    nearest_docks,
    world_docks,
    world_positions,
)


bsdiff4 = pytest.importorskip("bsdiff4")

from tools.build_ap_basepatch import PATCHES, vanilla_image


ELCID, TREADOOL, ANCIENT_CAVE_FINAL_FLOOR = 0x03, 0x7A, 0xF1
ELCID_DOCK = 0xC8
LAST_DOCK = 0xE6
LDA_LONG_X, STA_ABS = 0xBF, 0x8D
PENDING_DOCK = 0x09EE
OLD_TREADOOL_DOCK = bytes([0xA9, 0x01, STA_ABS, *PENDING_DOCK.to_bytes(2, "little")])
"""The old ``LDA #$01 : STA $09EE`` (as 7D(01))."""


def test_world_docks_are_the_warp_docks() -> None:
    docks = world_docks()
    assert list(docks) == list(range(FIRST_TOWN_DOCK, LAST_DOCK + 1))
    assert docks[ELCID_DOCK] == (43, 217)
    assert docks[TREADOOL_DOCK] == (175, 47)


def test_town_positions_come_from_their_world_exits() -> None:
    positions = world_positions()
    assert positions[ELCID] == (40, 218)
    assert positions[ELCID + 1] == (40, 218), "Elcid's houses take Elcid's position"
    assert positions[TREADOOL] == (176, 46)
    assert ANCIENT_CAVE_FINAL_FLOOR not in positions


def test_nearest_dock_wraps_around_the_world() -> None:
    docks = {1: (250, 10), 2: (20, 10)}
    assert nearest_dock((5, 10), docks) == 1
    assert nearest_dock((15, 10), docks) == 2  # noqa: PLR2004 - a dock id
    assert nearest_dock((135, 10), {1: (130, 10), 2: (140, 10)}) == 1, "a tie goes to the first listed"


def test_table() -> None:
    table = nearest_docks()
    assert len(table) == TABLE_SIZE
    assert set(table) <= set(range(FIRST_TOWN_DOCK, LAST_DOCK + 1))
    assert table[ELCID] == ELCID_DOCK
    assert table[TREADOOL] == TREADOOL_DOCK
    assert table[ANCIENT_CAVE_FINAL_FLOOR] == TREADOOL_DOCK, "no way to the world map: Treadool's, as before"


@pytest.fixture(scope="module")
def base_roms() -> list[bytes]:
    """The linear and the open-world base ROM."""
    vanilla = vanilla_image(files.original_file)
    return [bsdiff4.patch(vanilla, patch_file.read_bytes()) for patch_file, _ in PATCHES]


def test_ship_state_reads_the_table(base_roms: list[bytes]) -> None:
    store = bytes([STA_ABS, *PENDING_DOCK.to_bytes(2, "little")])
    for rom in base_roms:
        code = rom[RX_CODE_REGION.start : RX_CODE_REGION.stop]
        assert OLD_TREADOOL_DOCK not in code
        at = code.index(store) - 4
        assert code[at] == LDA_LONG_X, "LDA.l NearestDock,x : STA $09EE"
        table = address_from_lorom(int.from_bytes(code[at + 1 : at + 4], "little"))
        assert table + TABLE_SIZE <= RX_CODE_REGION.stop
        entries = rom[table : table + TABLE_SIZE]
        assert entries[ELCID] == ELCID_DOCK
        assert entries[TREADOOL] == TREADOOL_DOCK
        assert set(entries) <= set(range(FIRST_TOWN_DOCK, LAST_DOCK + 1))
