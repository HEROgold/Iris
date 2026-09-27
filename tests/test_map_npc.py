"""add_npc/remove_npc (Phase 5 of the map-content strategy).

Adding an NPC can't be written yet: it grows the event container, and containers can't leave banks $80-$BF
(HER-232). The round trip returns once events have room there.

Uses Elcid (map 0x03), the map `patches/HEROgold/party_toggle.py` edits in place.
"""

import pytest

from errors import EventFreeSpaceError
from helpers.files import new_file, write_file
from structures.event_script.instructions import Instruction
from structures.map_npc import add_npc
from structures.zone import Zone
from tests.reset_file import reset_file


_MAP_INDEX = 0x03  # Elcid
_END_OPCODE = 0x00


def test_adding_an_npc_refuses_to_move_the_event_container_out_of_banks_80_to_bf() -> None:
    """HER-232: a new NPC grows the map's NPC-load script, which moved the event container to the expansion area.
    That broke the map in an emulator (the interpreter needs scripts in banks $80-$BF), so writing raises and the
    event data stays as it was."""
    try:
        zone = Zone.from_index(_MAP_INDEX)
        add_npc(zone, x=10, y=12, sprite_index=5, talk_instructions=[Instruction(0, _END_OPCODE, [])])
        assert zone.event.npc_script.dirty
        write_file.flush()
        before = new_file.read_bytes()
        with pytest.raises(EventFreeSpaceError, match=r"\$80-\$BF"):
            zone.write_events()
        write_file.flush()
        assert new_file.read_bytes() == before
    finally:
        reset_file()
