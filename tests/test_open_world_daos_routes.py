"""Open world's two ways to Daos, ported from terrorwave's open-world events (Iris-Dev#75).

Nothing else leads into the Shrine of Daos in open world: no exit does, and the story's warps start from scenes
open world empties. So the open-world base has both, each behind exactly the gate the apworld's logic models, and the
linear base has neither.
"""

from collections.abc import Iterator

import pytest
from iris.enums.flags import EventFlag
from iris.helpers import files
from iris.helpers.files import session, use
from iris.structures.event_script import MapEvent
from iris.structures.event_script.containers import reset_map_events
from iris.structures.event_script.dump import _signature
from iris.structures.event_script.instructions import Address, Instruction
from iris.structures.event_script.script import EventScript
from iris.structures.maiden import Clare, Lisa, Marie
from iris.structures.zone import Zone
from iris.tables import MapEventObject, select, selected


pytest.importorskip("bsdiff4")

from iris.build import build
from tools.build_ap_basepatch import OPEN_WORLD_OPTIONS, OPTIONS, vanilla_image


CONDITION, SET_FLAG, WARP, LOAD_NPC = 0x14, 0x1A, 0x16, 0x68
ENGINE = 0x1C1
IRIS_TREASURES = range(0x19C, 0x1A6)
"""The ten items the curator takes (the last, 0x1A5, stands for the Ancient Cave's tenth treasure)."""
TREASURES_RETURNED = 0x0E
"""The variable the curator (69-B-59) counts returned treasures in."""
PORTRAVIA_LAB, GRUBERIK_LOBBY = 0xA2, 0x69
DOCK_TILE = 0x0A
SAGE, SAGE_NPC = 0x6D, 0x1E
"""The new NPC's talk script and sprite: NPC 0x1E is talk script 0x4F + 0x1E."""
DOOM_ISLAND = (0xE6, 0x63, 0x01)
"""The shrine's entrance scene, E6-A-63, which walks on to E7-A-62."""
INSIDE_THE_SHRINE = (0xE7, 0x62, 0x01)
DOCK = f"{PORTRAVIA_LAB:02X}-C-{DOCK_TILE:02X}"
"""The dock tile's script, in Iris's letters (terrorwave's A2-D-0A)."""
SAGE_TALK = f"{GRUBERIK_LOBBY:02X}-B-{SAGE:02X}"


@pytest.fixture(autouse=True)
def _restore() -> Iterator[None]:
    rom, patch = session(), selected()
    yield
    select(patch)
    use(rom)


def _scripts() -> dict[str, EventScript]:
    reset_map_events()
    scripts = {}
    for index in range(MapEventObject.count):
        map_event = MapEvent.from_index(index)
        map_event.read()
        for event_list in map_event.event_lists:
            for script in event_list.events:
                scripts[_signature(index, script)] = script
        scripts[f"{index:02X}-X-XX"] = map_event.npc_script
    return scripts


def _condition(ins: Instruction) -> list[object]:
    """A ``0x14`` chain's operands with its jump target blanked out."""
    assert ins.opcode == CONDITION
    return [None if isinstance(operand, Address) else operand for operand in ins.operands]


def _ops(script: EventScript) -> list[tuple[int, list[object]]]:
    return [(ins.opcode, list(ins.operands)) for ins in script.instructions]


def _warps_to(scripts: dict[str, EventScript], target: tuple[int, int, int]) -> set[str]:
    return {sig for sig, script in scripts.items() if (WARP, list(target)) in _ops(script)}


@pytest.fixture(scope="module")
def image() -> bytes:
    return vanilla_image(files.original_file)


def test_the_maiden_flags_are_the_ones_the_rx_sets() -> None:
    """rx_specials.asm sets flag 0x1A + m for maiden m (MaidenMask $04,$08,$10 on $077E+3)."""
    assert [maiden.my_maiden_flag for maiden in (Lisa, Marie, Clare)] == [0x1A, 0x1B, 0x1C]


def test_open_world_flies_to_doom_island_from_the_portravia_lab(image: bytes) -> None:
    build(image, OPEN_WORLD_OPTIONS)
    scripts = _scripts()
    dock = scripts[DOCK]
    gates = [_condition(ins) for ins in dock.instructions[:2]]
    assert gates == [
        [0x00, Lisa.my_maiden_flag, 0x80, Marie.my_maiden_flag, 0x80, Clare.my_maiden_flag, 0x30, None, 0xFF],
        [0xC2, ENGINE, 0x01, 0x30, None, 0xFF],
    ]
    assert (WARP, list(DOOM_ISLAND)) in _ops(dock)
    assert DOCK_TILE in {tile.index for tile in Zone.from_index(PORTRAVIA_LAB).data.tiles}
    assert _warps_to(scripts, DOOM_ISLAND) == {DOCK, "EB-A-03"}  # EB-A-03 is the story's, unreachable


def test_open_world_warps_into_the_shrine_for_the_iris_treasures(image: bytes) -> None:
    build(image, OPEN_WORLD_OPTIONS)
    scripts = _scripts()
    sage = scripts[SAGE_TALK]
    assert _condition(sage.instructions[0]) == [0x12, TREASURES_RETURNED, 0x0A, 0x20, None, 0xFF]
    ops = _ops(sage)
    assert (SET_FLAG, [int(EventFlag.DAOS_DEFEATED)]) in ops
    assert ops.index((SET_FLAG, [int(EventFlag.DAOS_DEFEATED)])) < ops.index((WARP, list(INSIDE_THE_SHRINE)))
    assert (LOAD_NPC, [SAGE, SAGE]) in _ops(scripts[f"{GRUBERIK_LOBBY:02X}-X-XX"])
    assert SAGE_NPC in {npc.index for npc in Zone.from_index(GRUBERIK_LOBBY).data.npc_positions}

    # Holding a treasure sets its found flag, which the curator needs before it takes the treasure.
    found = scripts[f"{GRUBERIK_LOBBY:02X}-X-02"]
    pairs = list(zip(found.instructions[::2], found.instructions[1::2], strict=False))
    found_flag = int(EventFlag.IRIS_TREASURE_01)
    assert [(_condition(test), (flag.opcode, flag.operands)) for test, flag in pairs] == [
        ([0xC2, item, 0x01, 0x30, None, 0xFF], (SET_FLAG, [found_flag + n])) for n, item in enumerate(IRIS_TREASURES)
    ]


def test_linear_has_neither_way(image: bytes) -> None:
    build(image, OPTIONS)
    scripts = _scripts()
    assert DOCK not in scripts
    assert SAGE_TALK not in scripts
    assert _warps_to(scripts, DOOM_ISLAND) == {"EB-A-03"}
    assert DOCK_TILE not in {tile.index for tile in Zone.from_index(PORTRAVIA_LAB).data.tiles}
