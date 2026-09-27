"""Event-container growth: a script that no longer fits its slot can't move the container out of banks $80-$BF.

An emulator check (HER-232) showed a container moved to the expansion area breaks the map: the event interpreter
reads its RAM variables through the script's data bank, and banks $C0-$FF don't mirror WRAM. Iris has no free space
inside banks $80-$BF for a whole container, so growth raises instead of writing a broken ROM.
"""

import pytest

from errors import EventFreeSpaceError
from helpers.files import output_bytes, write_file
from structures.event_script import MapEvent
from structures.event_script.containers import EventScript
from structures.event_script.instructions import Instruction
from tests.reset_file import reset_file


_MAP_INDEX = 0x06
_PADDING_OPCODE = 0x11  # a real, single-byte, no-operand opcode (see opcodes.py)


def _find_growable_script(map_event: MapEvent) -> EventScript:
    """A non-NPC script Iris has actually parsed, to append a harmless instruction to."""
    for event_list in map_event.event_lists[1:]:
        for event in event_list.events:
            if event.instructions:
                return event
    msg = f"Map {_MAP_INDEX:#04x} has no parseable class-list script to test with."
    raise AssertionError(msg)


def test_overflowing_a_script_refuses_to_move_the_container_out_of_banks_80_to_bf() -> None:
    """HER-232: the event interpreter sets the data bank to the script's bank and reads its own RAM variables
    with 16-bit addresses, which only reach WRAM in banks $80-$BF. A container moved to the expansion area
    (banks $E0+) played as a broken map in an emulator, so relocation raises and writes nothing."""
    try:
        map_event = MapEvent.from_index(_MAP_INDEX)
        script = _find_growable_script(map_event)
        script.instructions.append(Instruction(len(script.raw), _PADDING_OPCODE, []))
        script.dirty = True
        assert map_event._needs_relocation()  # noqa: SLF001 (confirm the overflow was actually detected)
        write_file.flush()
        before = output_bytes()

        with pytest.raises(EventFreeSpaceError, match=r"\$80-\$BF"):
            map_event.write()
        write_file.flush()
        assert output_bytes() == before
    finally:
        reset_file()
