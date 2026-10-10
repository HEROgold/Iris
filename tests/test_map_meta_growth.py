"""Growth round-trip test for MapMeta/ZoneData relocation (Phase 3 of the map-content strategy).

`tests/read_write.py::test_map_meta` only proves *identity* (read -> write unchanged -> still the
same bytes). This proves relocation actually works end to end: add a new exit (growing the blob
past its original size, so it cannot be written in place), write, then read the relocated bytes
back straight from the ROM to confirm both the new data and the repointed 0x27FCBC entry survive.

Deliberately does NOT re-parse via ``ZoneData(new_pointer)``, so the check doesn't depend on the code under test:
verification reads the session's image (``output_bytes()``) and replicates just enough of
``ZoneData._parse_offsets``'s section-extraction to check section 2, independent of any ``ZoneData``/cache state.

Caveat: like the rest of this suite, ZoneData._cache/MapMeta don't get reset between tests, only the
ROM bytes do (via reset_file). Pick a map index no other test in this session touches.
"""

from helpers.addresses import address_from_lorom
from helpers.files import output_bytes, write_file
from structures.map_meta import MapMeta
from structures.zone import Boundary, Exit
from tables import MapMetaObject
from tests.reset_file import reset_file


_MAP_INDEX = 0x06  # documented in the lufia2-object-layout skill: 5 exits, 16 NPCs, 3 chests
_EXIT_SECTION = 2
_EXIT_RECORD_SIZE = 9


def _read_section(rom: bytes, blob_start: int, section_index: int) -> bytes:
    """Extract one section's raw bytes from a ZoneData blob, mirroring ZoneData._parse_offsets."""
    size = int.from_bytes(rom[blob_start:blob_start + 2], "little")
    data = rom[blob_start + 2:blob_start + 2 + size]
    offsets = [int.from_bytes(data[i * 2:i * 2 + 2], "little") for i in range(21)]
    clean_offsets = sorted(set(offsets))
    offset = offsets[section_index]
    index = clean_offsets.index(offset)
    next_offset = size if index == len(clean_offsets) - 1 else clean_offsets[index + 1]
    return data[offset - 2:next_offset - 2]


def test_adding_an_exit_relocates_zonedata_and_repoints_the_table() -> None:
    try:
        meta = MapMeta.from_index(_MAP_INDEX)
        original_pointer = meta.zone_data_pointer
        zone_data = meta.zone_data
        original_exit_count = len(zone_data.exits)
        assert not zone_data.dirty

        new_exit = Exit(
            index=original_exit_count,
            boundary=Boundary(0, 0, 1, 1),
            misc=0,
            destination_x=5,
            destination_y=5,
            destination_map=_MAP_INDEX,
        )
        zone_data.set_exits([*zone_data.exits, new_exit])
        assert zone_data.dirty

        meta.write()
        write_file.flush()
        assert not zone_data.dirty, "write() should have cleared dirty after relocating"

        # Read the pointer table entry straight from the written ROM, independent of the (now
        # stale) MapMeta instance, to prove the table itself was actually repointed.
        rom = output_bytes()
        table_offset = MapMetaObject.address + _MAP_INDEX * MapMetaObject.reference_pointer
        raw = int.from_bytes(rom[table_offset:table_offset + 3], "little")
        new_pointer = address_from_lorom(raw)
        assert new_pointer != original_pointer, "the blob should have relocated, not stayed in place"
        assert new_pointer == zone_data.start

        # Independently parse section 2 out of the raw relocated bytes to prove the written data is
        # well-formed, not just that *a* pointer changed.
        section2 = _read_section(rom, new_pointer, _EXIT_SECTION)
        assert section2[-1] == 0xFF
        assert (len(section2) - 1) % _EXIT_RECORD_SIZE == 0
        records = [section2[i:i + _EXIT_RECORD_SIZE] for i in range(0, len(section2) - 1, _EXIT_RECORD_SIZE)]
        assert len(records) == original_exit_count + 1
        landed = records[-1]
        # record layout: [index, boundary(4), misc, dest_x, dest_y, dest_map]
        assert (landed[6], landed[7], landed[8]) == (5, 5, _MAP_INDEX)
    finally:
        reset_file()
