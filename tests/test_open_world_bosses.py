"""Open world's boss NPCs (Iris-Dev#43): placement, flags, and the scripts each NPC gets."""

from collections.abc import Iterator

import pytest

from iris.build import Options, build
from iris.constants import AP_OPT_BOSS_STRENGTH
from iris.enums.flags import EventFlag
from iris.enums.patches import Patch
from iris.helpers import files
from iris.helpers.files import open_rom, session, use
from iris.patches.open_world import apply_open_world
from iris.patches.open_world.bosses import (
    BOSSES,
    DAOS,
    SPOTS,
    BOSS_SCALING_NONE,
    BOSS_SCALING_PARTY,
    STAT_DERIVE_CALL,
    _flags_of,
    boss_monsters,
    fixed_placement,
    place_bosses,
    shuffled_placement,
)
from iris.structures.event_script.containers import MapEvent, reset_map_events
from iris.structures.event_script.event_patch import resolve_or_create
from iris.structures.monster import Monster
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


def test_depth_scaling(source: bytes) -> None:
    """A boss at a spot deeper than its own story place gets stronger, and the other way round."""
    rom = session()
    try:
        build(source, Options(7, selected_patch=Patch.VANILLA, open_world=True))
        before = {b.name: Monster.level_from_index(boss_monsters(b)[0]) for b in BOSSES}
        build(source, Options(7, selected_patch=Patch.VANILLA, open_world=True, boss_strength="depth"))
        after = {b.name: Monster.level_from_index(boss_monsters(b)[0]) for b in BOSSES}
    finally:
        use(rom)
    placement = shuffled_placement(7)
    late = next(b for s, b in placement.items() if BOSSES.index(b) > SPOTS.index(s) * len(BOSSES) // len(SPOTS) + 3)
    assert after[late.name] < before[late.name]


def test_party_scaling_hooks_the_monster_loader(source: bytes) -> None:
    rom = session()
    try:
        out = build(source, Options(1, selected_patch=Patch.VANILLA, open_world=True, boss_strength="party"))
    finally:
        use(rom)
    address, vanilla = STAT_DERIVE_CALL
    assert out[address] == 0x22  # still a JSL, now to scale_boss
    assert out[address : address + 4] != vanilla
    assert out[AP_OPT_BOSS_STRENGTH] == BOSS_SCALING_PARTY


def test_archipelago_installs_boss_scaling_switched_off(source: bytes) -> None:
    """An Archipelago open-world build hooks the loader with mode 0; the world's tokens pick the mode per seed."""
    rom = session()
    try:
        out = build(source, Options(1, selected_patch=Patch.VANILLA, open_world=True, archipelago=True))
    finally:
        use(rom)
    address, vanilla = STAT_DERIVE_CALL
    assert out[address : address + 4] != vanilla
    assert out[AP_OPT_BOSS_STRENGTH] == BOSS_SCALING_NONE
