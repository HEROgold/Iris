"""terrorwave's event-patch format: commands, its class letters, new scripts, and NPC-load jumps that survive relocation."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from iris.enums.event_scripts import EventClass
from iris.helpers import files
from iris.helpers.files import open_rom, output_bytes, session, use
from iris.structures.event_script.containers import MapEvent
from iris.structures.event_script.event_patch import apply_event_patch, apply_event_patch_file, resolve_or_create
from iris.structures.event_script.instructions import Address
from iris.structures.zone import Boundary, Zone, move_all_zone_data


PATCHES = Path(__file__).parents[1] / "src" / "iris" / "patches" / "absynnonym"
SKILLS_CAVE = 0x05
OVERWORLD = 0x00


@pytest.fixture(autouse=True)
def fresh_rom() -> Iterator[None]:
    rom = session()
    open_rom(files.original_file.read_bytes())
    move_all_zone_data()  # frees the event pool, as the Archipelago build does first
    yield
    use(rom)


def _reopen() -> None:
    """Parse everything again from the written bytes."""
    open_rom(output_bytes())


def test_commands() -> None:
    apply_event_patch(
        "!npc 0f (00) 05:17,2e\n"
        "!npc +1 (0B) 05:16<=1c<=21,2f<=31<=33\n"
        "!exit +1 (40) 00:c8,20->d6:18,23 2x2\n"
        "!tile 0a 05:0a,0c 3x2\n",
    )
    _reopen()
    cave = Zone.from_index(SKILLS_CAVE).data
    npcs = {npc.index: npc for npc in cave.npc_positions}
    assert (npcs[0x0F].x, npcs[0x0F].y, npcs[0x0F].boundary) == (0x17, 0x2E, Boundary(0x17, 0x2E, 0x18, 0x2F))
    walker = npcs[max(npcs)]
    assert (walker.x, walker.y, walker.misc) == (0x1C, 0x31, 0x0B)
    assert walker.boundary == Boundary(0x16, 0x2F, 0x22, 0x34)
    tile = next(tile for tile in cave.tiles if tile.index == 0x0A)
    assert tile.boundary == Boundary(0x0A, 0x0C, 0x0D, 0x0E)
    new_exit = max(Zone.from_index(OVERWORLD).data.exits, key=lambda exit_: exit_.index)
    assert new_exit.boundary == Boundary(0xC8, 0x20, 0xCA, 0x22)
    assert (new_exit.misc, new_exit.destination_map, new_exit.destination_x, new_exit.destination_y) == (0x40, 0xD6, 0x18, 0x23)


def test_class_letters_are_terrorwaves() -> None:
    """terrorwave's C is Iris's B (talk scripts) and its D is Iris's C (tile scripts)."""
    assert resolve_or_create("05-C-11").event_class is EventClass.REFERENCED
    assert resolve_or_create("05-D-01").event_class is EventClass.NPC
    assert resolve_or_create("05-A-00").event_class is EventClass.SETUP_MAP
    assert resolve_or_create("05-X-XX") is MapEvent.from_index(SKILLS_CAVE).npc_script


def test_new_script_is_created() -> None:
    apply_event_patch("EVENT 05-C-5E\n0000. 08: Hello.<END EVENT>\n")
    _reopen()
    script = resolve_or_create("05-C-5E")
    assert script.pointer  # read from the ROM, not created again
    assert script.instructions[0].opcode == 0x08


def test_double_import_is_refused() -> None:
    with pytest.raises(ValueError, match="twice"):
        apply_event_patch("EVENT 05-C-11\n0000. 00()\nEVENT 05-C-11\n0000. 00()\n")


def test_npc_load_jumps_survive_relocation() -> None:
    """Map 1D's NPC-load script branches; its container moves, and the jumps must still land inside the script.

    The game bases an NPC-load script's jumps on its own 32KB bank, not on the event-list header.
    """
    apply_event_patch_file(PATCHES / "eventpatch_open_world_base.txt")
    _reopen()
    script = MapEvent.from_index(0x1D).npc_script
    assert script.pointer >= 0x80000  # moved into the event pool
    assert script.base_pointer == script.pointer & 0xFF8000
    jumps = [op for ins in script.instructions for op in ins.operands if isinstance(op, Address)]
    assert jumps
    assert all(jump.is_local for jump in jumps)
    lines = {ins.line for ins in script.instructions}
    assert all(jump.offset in lines for jump in jumps)
