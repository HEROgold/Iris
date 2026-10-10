"""FRUE's talk scripts jump into their neighbours' bytes; Iris keeps those jumps and protects their targets."""

from collections.abc import Iterator

import pytest

from iris.enums.patches import Patch
from iris.helpers import files
from iris.helpers.files import open_rom, session, use
from iris.structures.event_script.compiler import compile_script
from iris.structures.event_script.containers import MapEvent
from iris.structures.event_script.instructions import Address
from iris.structures.event_script.script import EventScript
from iris.tables import select, selected


JUMPING_MAPS = (0x3E, 0xA0, 0xB5)


@pytest.fixture
def frue() -> Iterator[None]:
    rom, patch = session(), selected()
    select(Patch.FRUE)
    open_rom(files.original_file.read_bytes(), base=Patch.FRUE)
    yield
    select(patch)
    use(rom)


def _scripts(map_index: int) -> list[EventScript]:
    map_event = MapEvent.from_index(map_index)
    map_event.read()
    return [event for event_list in map_event.event_lists for event in event_list.events]


def test_vanilla_has_no_outside_jumps() -> None:
    assert not [s for i in JUMPING_MAPS for s in _scripts(i) if s.external_jumps]


@pytest.mark.usefixtures("frue")
def test_frue_jumps_recompile_unchanged() -> None:
    jumping = [s for i in JUMPING_MAPS for s in _scripts(i) if s.external_jumps]
    assert len(jumping) == len(JUMPING_MAPS)
    for script in jumping:
        data = compile_script(script, script_pointer=script.pointer)
        assert script.raw.startswith(data)


@pytest.mark.usefixtures("frue")
def test_jump_targets_refuse_rewrites() -> None:
    targets = [s for i in JUMPING_MAPS for s in _scripts(i) if s.jumped_into]
    assert len(targets) == len(JUMPING_MAPS)
    targets[0].dirty = True
    with pytest.raises(ValueError, match="jumps into its bytes"):
        targets[0].write()
    targets[0].dirty = False


@pytest.mark.usefixtures("frue")
def test_maps_with_outside_jumps_refuse_relocation() -> None:
    with pytest.raises(ValueError, match="edited in place"):
        MapEvent.from_index(JUMPING_MAPS[0]).write_relocated()


def test_non_local_address_renders_raw() -> None:
    assert repr(Address(0x13B, is_local=False)) == "$13B"
    assert repr(Address(0x13B)) == "@13B"
