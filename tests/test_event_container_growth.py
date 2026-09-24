"""Growth round-trip test for the event-container relocator (Phase 4 of the map-content strategy).

Mirrors test_map_meta_growth.py's approach: force an overflow (append an instruction to a script so
its recompiled bytes exceed the original slot), write, then independently decode the raw new_file
bytes -- the MapEventObject record, the event-list header, and the script's own bytes -- to confirm
the container actually relocated and the new bytes are self-consistent. Never re-parses via
MapEvent.from_index/EventScript, since read_file is always the pristine original ROM (see
test_map_meta_growth.py's docstring) and can't see anything written only to write_file/new_file.
"""

from constants import EVENT_SCRIPT_FREESPACE
from structures.event_script import MapEvent
from structures.event_script.containers import EventScript
from structures.event_script.instructions import Instruction
from helpers.files import new_file, write_file
from tables import MapEventObject
from tests.reset_file import reset_file


_MAP_INDEX = 0x06
_PADDING_OPCODE = 0x11  # a real, single-byte, no-operand opcode (see opcodes.py)


def _decode_bank_extended_offset(low: bytes, high: bytes) -> int:
    return int.from_bytes(low, "little") | (int.from_bytes(high, "little") << 15)


def _find_growable_script(map_event: MapEvent) -> EventScript:
    """A non-NPC script Iris has actually parsed, to append a harmless instruction to."""
    for event_list in map_event.event_lists[1:]:
        for event in event_list.events:
            if event.instructions:
                return event
    msg = f"Map {_MAP_INDEX:#04x} has no parseable class-list script to test with."
    raise AssertionError(msg)


def test_overflowing_a_script_relocates_the_whole_container() -> None:
    try:
        map_event = MapEvent.from_index(_MAP_INDEX)
        script = _find_growable_script(map_event)
        original_len = len(script.raw)
        original_header_base = map_event.event_list_pointer
        original_script_pointer = script.pointer

        script.instructions.append(Instruction(original_len, _PADDING_OPCODE, []))
        script.dirty = True
        assert map_event._needs_relocation()  # noqa: SLF001 (confirm the overflow was actually detected)

        map_event.write()
        write_file.flush()
        assert not script.dirty, "write() should have cleared dirty after relocating"

        rom = new_file.read_bytes()
        record_offset = MapEventObject.address + _MAP_INDEX * MapEventObject.size
        eventlist_low = rom[record_offset:record_offset + 2]
        eventlist_high = rom[record_offset + 2:record_offset + 3]
        eventlist_offset = _decode_bank_extended_offset(eventlist_low, eventlist_high)
        new_header_base = map_event.base_pointer + eventlist_offset
        assert new_header_base == script.base_pointer, "the record should point at the relocated header"
        assert new_header_base != original_header_base, "the container should have relocated, not stayed put"
        assert script.pointer != original_script_pointer
        assert new_header_base in EVENT_SCRIPT_FREESPACE, "should land in the reserved event-script pool"
        assert rom[new_header_base:new_header_base + 2] == b"PH"

        # The script's own bytes should now sit, in full, at its relocated address, ending in the
        # padding opcode appended above.
        assert rom[script.pointer:script.pointer + len(script.raw)] == script.raw
        assert script.raw[-1] == _PADDING_OPCODE
        assert len(script.raw) == original_len + 1
    finally:
        reset_file()
