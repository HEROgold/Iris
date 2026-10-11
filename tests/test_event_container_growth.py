"""Event-container growth: a script that no longer fits its slot moves its whole container, within banks $80-$BF.

An emulator check (HER-232) showed a container moved to the expansion area breaks the map: the event interpreter
reads its RAM variables through the script's data bank, and banks $C0-$FF don't mirror WRAM. The only room inside
banks $80-$BF is what ``move_all_zone_data`` frees in banks $91-$94; without it, growth raises instead of writing a
broken ROM.
"""

import pytest

from iris.errors import EventFreeSpaceError
from iris.helpers.files import open_rom, original_file, output_bytes, read_file
from iris.structures.event_script import MapEvent
from iris.structures.event_script.containers import EVENT_BANK_LIMIT, EventScript, reset_map_events
from iris.structures.event_script.instructions import Instruction
from iris.structures.zone import move_all_zone_data


_MAP_INDEX = 0x06
_PADDING_OPCODE = 0x11  # a real, single-byte, no-operand opcode (see opcodes.py)
_GROWTH = 64
"""Bytes appended: more than compressing the text again could win back."""
_ZONE_DATA_BANKS = range(0x88000, 0xA8000)


def _find_growable_script(map_event: MapEvent) -> EventScript:
    """A non-NPC script Iris has actually parsed, to append harmless instructions to."""
    for event_list in map_event.event_lists[1:]:
        for event in event_list.events:
            if event.instructions:
                return event
    msg = f"Map {_MAP_INDEX:#04x} has no parseable class-list script to test with."
    raise AssertionError(msg)


def _grow(script: EventScript) -> None:
    end = script.instructions[-1].line + 0x100
    script.instructions.extend(Instruction(end + i, _PADDING_OPCODE, []) for i in range(_GROWTH))
    script.dirty = True


def test_overflowing_a_script_without_room_raises() -> None:
    """Before ZoneData moves out, there is no room in banks $80-$BF: relocation raises and writes nothing."""
    try:
        map_event = MapEvent.from_index(_MAP_INDEX)
        _grow(_find_growable_script(map_event))
        assert map_event._needs_relocation()  # noqa: SLF001 (confirm the overflow was actually detected)
        before = output_bytes()

        with pytest.raises(EventFreeSpaceError, match=r"\$80-\$BF"):
            map_event.write()
        assert output_bytes() == before
    finally:
        open_rom(original_file)


def test_overflowing_a_script_moves_the_container_into_the_space_zone_data_left() -> None:
    try:
        move_all_zone_data()
        map_event = MapEvent.from_index(_MAP_INDEX)
        map_event.read()
        script = _find_growable_script(map_event)
        old_pointer, old_size = script.pointer, len(script.raw)
        _grow(script)
        expected = [(instruction.opcode, instruction.operands) for instruction in script.instructions]
        old_bytes = output_bytes()[old_pointer : old_pointer + old_size]

        map_event.write()

        assert map_event.event_list_pointer in _ZONE_DATA_BANKS
        assert map_event.event_list_pointer < EVENT_BANK_LIMIT
        assert output_bytes()[old_pointer : old_pointer + old_size] == old_bytes  # left for whatever still reads it

        reset_map_events()  # parse the map again, from the bytes just written
        reread = MapEvent.from_index(_MAP_INDEX)
        reread.read()
        moved = next(
            event
            for event_list in reread.event_lists
            for event in event_list.events
            if (event.event_class, event.index) == (script.event_class, script.index)
        )
        assert moved.pointer in _ZONE_DATA_BANKS
        assert [instruction.opcode for instruction in moved.instructions] == [opcode for opcode, _ in expected]
        read_file.seek(moved.pointer)
        assert read_file.read(len(moved.raw)) == moved.raw
    finally:
        open_rom(original_file)
