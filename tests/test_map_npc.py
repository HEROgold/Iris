"""Round-trip test for add_npc/remove_npc (Phase 5 of the map-content strategy).

Uses Elcid (map 0x03) -- untouched by any other growth test in this session, and the same map
`patches/HEROgold/party_toggle.py` already uses for real NPC-script work. Verifies both add and
remove end to end by reading raw `new_file` bytes directly (never re-parsing through ZoneData/
MapEvent's normal constructors, which read via `read_file` -- always the pristine original ROM; see
test_map_meta_growth.py's docstring for why that can never see anything relocation-only wrote).
"""

from helpers.addresses import address_from_lorom
from helpers.files import new_file, write_file
from structures.event_script.instructions import Instruction
from structures.map_npc import add_npc, remove_npc
from structures.map_meta import MapMeta
from structures.zone import Zone
from tables import MapMetaObject
from tests.reset_file import reset_file


_MAP_INDEX = 0x03  # Elcid
_END_OPCODE = 0x00
_SPRITE_OPCODE = 0x68


def _read_section(rom: bytes, blob_start: int, section_index: int) -> bytes:
    """Extract one ZoneData section's raw bytes, mirroring ZoneData._parse_offsets."""
    size = int.from_bytes(rom[blob_start:blob_start + 2], "little")
    data = rom[blob_start + 2:blob_start + 2 + size]
    offsets = [int.from_bytes(data[i * 2:i * 2 + 2], "little") for i in range(21)]
    clean_offsets = sorted(set(offsets))
    offset = offsets[section_index]
    index = clean_offsets.index(offset)
    next_offset = size if index == len(clean_offsets) - 1 else clean_offsets[index + 1]
    return data[offset - 2:next_offset - 2]


def _current_zone_data_pointer(rom: bytes) -> int:
    table_offset = MapMetaObject.address + _MAP_INDEX * MapMetaObject.reference_pointer
    raw = int.from_bytes(rom[table_offset:table_offset + 3], "little")
    return address_from_lorom(raw)


def test_add_then_remove_npc_round_trips() -> None:
    try:
        zone = Zone.from_index(_MAP_INDEX)
        meta = MapMeta.from_index(_MAP_INDEX)
        original_npc_count = len(zone.data.npc_positions)
        original_npc_script_len = len(zone.event.npc_script.raw)

        # --- add ---
        npc = add_npc(
            zone,
            x=10,
            y=12,
            sprite_index=5,
            talk_instructions=[Instruction(0, _END_OPCODE, [])],
        )
        assert zone.data.dirty
        assert zone.event.npc_script.dirty

        meta.write()
        zone.write_events()
        write_file.flush()
        assert not zone.data.dirty
        assert not zone.event.npc_script.dirty

        rom = new_file.read_bytes()

        # ZoneData: section 7 grew by exactly one record, matching the new position.
        blob_start = _current_zone_data_pointer(rom)
        section7 = _read_section(rom, blob_start, 7)
        assert section7[-1] == 0xFF
        records = [section7[i:i + 8] for i in range(0, len(section7) - 1, 8)]
        assert len(records) == original_npc_count + 1
        assert records[-1] == bytes(npc.position)

        # NPC-load script: the new 0x68 instruction is the last 3 bytes, at its relocated address.
        npc_script = zone.event.npc_script
        assert len(npc_script.raw) == original_npc_script_len + 3
        assert rom[npc_script.pointer:npc_script.pointer + len(npc_script.raw)] == npc_script.raw
        assert npc_script.raw[-3:] == bytes([_SPRITE_OPCODE, npc.npc_slot, 5])

        # Talk script: a single END opcode, at its own relocated address.
        assert npc.talk_script is not None
        assert npc.talk_script.raw == bytes([_END_OPCODE])
        assert rom[npc.talk_script.pointer:npc.talk_script.pointer + 1] == bytes([_END_OPCODE])

        npc_script_pointer_after_add = npc_script.pointer

        # --- remove ---
        remove_npc(npc)
        assert zone.data.dirty
        assert npc_script.dirty

        meta.write()
        zone.write_events()
        write_file.flush()

        rom = new_file.read_bytes()
        blob_start = _current_zone_data_pointer(rom)
        section7 = _read_section(rom, blob_start, 7)
        records = [section7[i:i + 8] for i in range(0, len(section7) - 1, 8)]
        assert len(records) == original_npc_count

        # Shrinking never overflows, so this should have written in place (no further relocation).
        assert npc_script.pointer == npc_script_pointer_after_add
        assert len(npc_script.raw) == original_npc_script_len
        assert rom[npc_script.pointer:npc_script.pointer + len(npc_script.raw)] == npc_script.raw
    finally:
        reset_file()
