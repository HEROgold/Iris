"""Open world's boss NPCs (Iris-Dev#43): placement, flags, and the scripts each NPC gets."""

from collections.abc import Iterator

import pytest

from iris.enums.flags import EventFlag
from iris.helpers import files
from iris.helpers.files import open_rom, session, use
from iris.patches.open_world import apply_open_world
from iris.patches.open_world.bosses import (
    BOSSES,
    DAOS,
    SPOTS,
    _flags_of,
    fixed_placement,
    place_bosses,
    shuffled_placement,
)
from iris.structures.event_script.containers import MapEvent, reset_map_events
from iris.structures.event_script.event_patch import resolve_or_create
from iris.structures.zone import move_all_zone_data
from iris.tables import MapEventObject


@pytest.fixture(scope="module")
def source() -> bytes:
    return files.original_file.read_bytes()


@pytest.fixture
def placed(source: bytes) -> Iterator[list]:
    rom = session()
    open_rom(source)
    move_all_zone_data()
    apply_open_world()
    yield place_bosses(fixed_placement())
    use(rom)


def test_fixed_placement_follows_the_story() -> None:
    placement = fixed_placement()
    assert list(placement) == list(SPOTS)
    order = [BOSSES.index(boss) for boss in placement.values()]
    assert order == sorted(order)
    assert set(placement.values()) == set(BOSSES)


def test_shuffled_placement_is_seeded() -> None:
    assert shuffled_placement(1) == shuffled_placement(1)
    assert shuffled_placement(1) != shuffled_placement(2)
    assert set(shuffled_placement(1).values()) == set(BOSSES)  # every boss stands somewhere


def test_every_spot_gets_a_boss_npc(placed: list) -> None:
    assert len(placed) == len(SPOTS) + 1
    assert placed[-1].boss == DAOS
    assert placed[-1].flag == int(EventFlag.DAOS_DEFEATED)
    flags = [npc.flag for npc in placed[:-1]]
    assert len(set(flags)) == len(flags)


def test_boss_npc_scripts(placed: list) -> None:
    reset_map_events()  # parse what was written
    for npc in placed[:-1]:
        letters = npc.signature.replace("-B-", "-C-")  # Iris's B is terrorwave's C
        talk = resolve_or_create(letters).instructions
        assert (0x53, [npc.boss.formation]) in [(ins.opcode, ins.operands) for ins in talk]
        assert sum(ins.opcode == 0x20 for ins in talk) == npc.spot.rewards
        assert (0x1A, [npc.flag]) in [(ins.opcode, ins.operands) for ins in talk]
        load = MapEvent.from_index(npc.spot.map_index).npc_script.instructions
        assert any(ins.opcode == 0x15 and ins.operands[0] == npc.flag for ins in load)  # two spots can share a map
        assert (0x68, [npc.npc_slot, npc.boss.sprite]) in [(ins.opcode, ins.operands) for ins in load]


def test_boss_flags_are_only_the_bosses(placed: list) -> None:
    """No script but a boss NPC's own reads or writes its flag."""
    reset_map_events()
    flags = {npc.flag for npc in placed[:-1]}
    own = {(npc.spot.map_index, npc.npc_slot) for npc in placed}
    for index in range(MapEventObject.count):
        map_event = MapEvent.from_index(index)
        for event_list in map_event.event_lists:
            for script in event_list.events:
                if (index, script.index) in own or script is map_event.npc_script:
                    continue
                assert not (_flags_of(script.instructions) & flags), (hex(index), script)
