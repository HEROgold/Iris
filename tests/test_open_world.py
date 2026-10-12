"""Open world (Iris-Dev#43), and the event write path it leans on: padding, text repair, jumps between scripts."""

from collections.abc import Iterator

import pytest

from iris.build import Options, build
from iris.enums.event_scripts import EventClass
from iris.enums.patches import Patch
from iris.helpers import files
from iris.helpers.files import open_rom, session, use
from iris.patches.open_world import EXTRAS, INESCAPABLE_MAPS, MAP_PROPERTIES, MAX_WORLD_CLOCK, NO_ESCAPE, apply_open_world
from iris.structures.event_script.codec import render_text
from iris.structures.event_script.containers import MapEvent, reset_map_events
from iris.structures.event_script.event_patch import apply_event_patch, apply_event_patch_file, resolve_or_create
from iris.structures.event_script.script import EventScript
from iris.patches.open_world.leader import OPENING, TOWN_SPRITES, set_leader
from iris.structures.character import party_flag_of
from iris.structures.monster import Monster
from iris.structures.shop import Shop
from iris.structures.sprites import OverSprite, TownSprite
from iris.structures.zone import move_all_zone_data
from iris.tables import MapEventObject, select, selected


ALL_EXTRAS = tuple(name for name in EXTRAS if name != "npc_cave_bridge_orb_guard")
"""Every extra that goes with the others (the orb guard stands where orb_check puts its item)."""


@pytest.fixture(autouse=True)
def _restore_session() -> Iterator[None]:
    rom, patch = session(), selected()
    verify_pointers, easy_mode = Shop.verify_pointers, Monster.easy_mode
    yield
    Shop.verify_pointers, Monster.easy_mode = verify_pointers, easy_mode
    select(patch)
    use(rom)


@pytest.fixture(scope="module")
def source() -> bytes:
    """The ROM conftest opened; once a test opens a session from bytes, ``original_file`` is gone."""
    return files.original_file.read_bytes()


def _open(source: bytes, patch: Patch = Patch.VANILLA) -> None:
    select(patch)
    open_rom(source, base=patch)
    move_all_zone_data()


def _text(script: EventScript) -> list[str]:
    return [render_text(op) for ins in script.instructions for op in ins.operands if isinstance(op, list)]


def _all_scripts() -> list[EventScript]:
    return [
        script
        for index in range(MapEventObject.count)
        for event_list in MapEvent.from_index(index).event_lists
        for script in event_list.events
    ]


def test_shortened_script_parses_clean(source: bytes) -> None:
    """A script rewritten shorter in place leaves END padding, which parses as nothing."""
    _open(source)
    apply_event_patch("EVENT 03-C-11\n0000. 08: Hi.<END EVENT>\n")
    reset_map_events()
    assert len(resolve_or_create("03-C-11").instructions) == 1


def test_overwritten_back_reference_is_repaired(source: bytes) -> None:
    """Sundletan's 09-C-59 copies text with <REPEAT> from bytes the world clock overwrites; it must read the same."""
    _open(source)
    before = _text(resolve_or_create("09-C-59"))
    apply_event_patch_file(MAX_WORLD_CLOCK)
    reset_map_events()
    assert _text(resolve_or_create("09-C-59"))[: len(before)] == before


def test_open_world_leaves_no_outside_jumps(source: bytes) -> None:
    """Parsed again after open world moved containers, every script still ends where it did (no stray jumps)."""
    _open(source)
    apply_open_world(ALL_EXTRAS)
    reset_map_events()
    assert not [script for script in _all_scripts() if script.external_jumps]


def test_jump_target_is_replaced_with_its_jumper(source: bytes) -> None:
    """FRUE's Merix 3E-C-50 jumps into 3E-C-51: 51 can be replaced only while 50 is replaced too."""
    _open(source, Patch.FRUE)
    with pytest.raises(ValueError, match="jumps into its bytes"):
        apply_event_patch("EVENT 3E-C-51\n0000. 08: Hi.<END EVENT>\n")
    _open(source, Patch.FRUE)
    apply_event_patch("EVENT 3E-C-50\n0000. 08: Hi.<END EVENT>\nEVENT 3E-C-51\n0000. 08: Bye.<END EVENT>\n")
    assert resolve_or_create("3E-C-51").event_class is EventClass.REFERENCED


@pytest.mark.parametrize("patch", [Patch.VANILLA, Patch.FRUE])
def test_build(source: bytes, patch: Patch) -> None:
    rom = build(source, Options(1, selected_patch=patch, open_world=True, open_world_extras=ALL_EXTRAS))
    assert rom


def test_build_with_archipelago(source: bytes) -> None:
    options = Options(1, selected_patch=Patch.VANILLA, open_world=True, archipelago=True, unlock_warps=False)
    assert build(source, options)


def test_npcs_need_open_world(source: bytes) -> None:
    with pytest.raises(ValueError, match="need open world"):
        build(source, Options(1, selected_patch=Patch.VANILLA, open_world_extras=ALL_EXTRAS[:1]))


def test_unknown_npc_is_refused(source: bytes) -> None:
    _open(source)
    with pytest.raises(ValueError, match="Unknown open-world extras"):
        apply_open_world(["npc_nobody"])


def test_orb_guard_and_orb_check_exclude_each_other(source: bytes) -> None:
    _open(source)
    with pytest.raises(ValueError, match="can't be used together"):
        apply_open_world(["npc_cave_bridge_orb_guard", "orb_check"])


def test_orb_check_grants_once(source: bytes) -> None:
    _open(source)
    apply_open_world(["orb_check"])
    reset_map_events()
    opcodes = [ins.opcode for ins in resolve_or_create("44-D-01").instructions]
    assert opcodes[0] == 0x15  # skip when flag 0x30 is set
    assert 0x20 in opcodes
    assert 0x1A in opcodes


def test_escapable_dungeons(source: bytes) -> None:
    _open(source)
    apply_open_world(["escapable_dungeons"])
    reset_map_events()
    for index in range(MapEventObject.count):
        bits = {
            int(ins.operands[0]) & NO_ESCAPE
            for ins in MapEvent.from_index(index).npc_script.instructions
            if ins.opcode == MAP_PROPERTIES
        }
        assert bits <= ({NO_ESCAPE} if index in INESCAPABLE_MAPS else {0}), hex(index)


@pytest.mark.parametrize("leader", [3, 4])  # Artea gets a new town sprite; Tia's party flag isn't index + 1
def test_leader(source: bytes, leader: int) -> None:
    """The first scene ends with the leader joining and Maxim leaving; the overworld sprite follows the leader."""
    _open(source)
    maxim_over = OverSprite.from_index(0).sprite_index
    apply_open_world()
    set_leader(leader)
    reset_map_events()
    tail = [(ins.opcode, ins.operands) for ins in resolve_or_create(OPENING).instructions[-6:]]
    assert tail[0] == (0x15, [party_flag_of(leader), tail[0][1][1]])
    assert tail[1:5] == [(0x2B, [leader]), (0x1A, [party_flag_of(leader)]), (0x2C, [0]), (0x1B, [party_flag_of(0)])]
    town = TownSprite.from_pointer(TOWN_SPRITES[leader]).sprite_pointer - TownSprite.from_pointer(TOWN_SPRITES[0]).sprite_pointer
    assert OverSprite.from_index(0).sprite_index == maxim_over + town
    exempt = resolve_or_create("03-B-02")  # Elcid's new-game entrance still walks Maxim
    assert any(ins.opcode == 0x33 and ins.operands[1] == 0 for ins in exempt.instructions)


def test_leader_needs_open_world(source: bytes) -> None:
    with pytest.raises(ValueError, match="need open world"):
        build(source, Options(1, selected_patch=Patch.VANILLA, leader=3))
