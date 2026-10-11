"""The base ROM's hint slots and moved grants, as the apworld writes them with tokens (Iris-Dev#33).

The base patch grows every hint NPC's talk script to a slot of at least ``HINT_SLOT_SIZE`` bytes, which moves its map's
event container into banks $91-$94. The exported offsets must point at the live scripts of the built ROM, not at the
old bytes the move leaves behind.
"""

import importlib.util
from collections.abc import Iterator
from types import ModuleType

import pytest

from iris.build import build
from iris.helpers import files
from iris.helpers.files import read_file, session, use, write_file
from iris.patches.archipelago.overworld.hint_npcs import HINT_FLAGS, HINT_SLOT_SIZE
from iris.structures.event_script import MapEvent
from iris.structures.event_script.containers import EVENT_BANK_LIMIT, reset_map_events
from iris.structures.event_script.dump import _signature
from iris.tables import select, selected


pytest.importorskip("bsdiff4")

from tools.build_ap_basepatch import OPTIONS, vanilla_image  # noqa: E402
from tools.export_ap_data import DATA_FILE  # noqa: E402


_SET_FLAG, _TEXT_BOX, _END_EVENT = 0x1A, 0x08, 0x00


@pytest.fixture(scope="module")
def data() -> ModuleType:
    spec = importlib.util.spec_from_file_location("lufia2ow_data", DATA_FILE)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def base_rom() -> Iterator[None]:
    """The built base ROM as the active session, parsed afresh; conftest's session comes back afterwards."""
    rom, patch = session(), selected()
    build(vanilla_image(files.original_file), OPTIONS)
    reset_map_events()
    yield
    select(patch)
    use(rom)


def _script_bytes(map_index: int, signature: str) -> tuple[int, bytes]:
    map_event = MapEvent.from_index(map_index)
    map_event.read()
    script = next(
        script for event_list in map_event.event_lists for script in event_list.events
        if _signature(map_index, script) == signature
    )
    return script.pointer, script.raw


def test_every_slot_is_big_enough_and_inside_banks_80_to_bf(data: ModuleType) -> None:
    assert len(data.HINT_NPCS) >= len(HINT_FLAGS)
    for _, signature, offset, size in data.HINT_NPCS:
        assert size >= HINT_SLOT_SIZE, signature
        assert offset + size <= EVENT_BANK_LIMIT, signature


@pytest.mark.usefixtures("base_rom")
def test_every_slot_is_its_npcs_live_script(data: ModuleType) -> None:
    for map_index, signature, offset, size in data.HINT_NPCS:
        pointer, raw = _script_bytes(map_index, signature)
        assert pointer == offset, signature
        assert len(raw) >= size, signature


@pytest.mark.usefixtures("base_rom")
def test_a_full_slot_reads_back_as_a_hint(data: ModuleType) -> None:
    """What the apworld writes: SET FLAG, text boxes up to the end of the slot, zeros after."""
    map_index, signature, offset, size = data.HINT_NPCS[0]
    text = (b"A" * 24 + b"\x03") * 2 + b"A" * 24
    script = bytes([_SET_FLAG, HINT_FLAGS[0]])
    while len(script) + len(text) + 2 <= size:
        script += bytes([_TEXT_BOX]) + text + b"\x01"
    script = script[:-1] + bytes([_END_EVENT])
    write_file.seek(offset)
    write_file.write(script.ljust(size, b"\0"))
    reset_map_events()

    pointer, raw = _script_bytes(map_index, signature)
    assert pointer == offset
    assert raw[: len(script)] == script


@pytest.mark.usefixtures("base_rom")
def test_every_grant_offset_holds_its_item(data: ModuleType) -> None:
    for _, signature, offset, item, _, _ in data.GRANTS:
        read_file.seek(offset - 1)
        opcode, low = read_file.read(2)
        assert (opcode, low) == (0x20 + (item >> 8), item & 0xFF), signature
