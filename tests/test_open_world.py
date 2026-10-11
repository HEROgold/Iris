"""Open world (Iris-Dev#43), and the event write path it leans on: padding, text repair, jumps between scripts."""

from collections.abc import Iterator

import pytest

from iris.build import Options, build
from iris.enums.event_scripts import EventClass
from iris.enums.patches import Patch
from iris.helpers import files
from iris.helpers.files import open_rom, session, use
from iris.patches.open_world import MAX_WORLD_CLOCK, NPCS, apply_open_world
from iris.structures.event_script.codec import render_text
from iris.structures.event_script.containers import MapEvent, reset_map_events
from iris.structures.event_script.event_patch import apply_event_patch, apply_event_patch_file, resolve_or_create
from iris.structures.event_script.script import EventScript
from iris.structures.monster import Monster
from iris.structures.shop import Shop
from iris.structures.zone import move_all_zone_data
from iris.tables import MapEventObject, select, selected


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
    apply_open_world(NPCS)
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
    rom = build(source, Options(1, selected_patch=patch, open_world=True, open_world_npcs=NPCS))
    assert rom


def test_build_with_archipelago(source: bytes) -> None:
    options = Options(1, selected_patch=Patch.VANILLA, open_world=True, archipelago=True, unlock_warps=False)
    assert build(source, options)


def test_npcs_need_open_world(source: bytes) -> None:
    with pytest.raises(ValueError, match="need open world"):
        build(source, Options(1, selected_patch=Patch.VANILLA, open_world_npcs=NPCS[:1]))


def test_unknown_npc_is_refused(source: bytes) -> None:
    _open(source)
    with pytest.raises(ValueError, match="Unknown open-world NPC"):
        apply_open_world(["npc_nobody"])
