"""``move_all_zone_data``: every map's ZoneData moves, unchanged, to the expansion area, and its old bytes in banks
$91-$94 become the event pool (the only room event containers can grow into, HER-232)."""

from iris.constants import ZONE_DATA_FREESPACE
from iris.helpers.files import open_rom, original_file, output_bytes, read_file
from iris.helpers.freespace import BANK_MASK, event_script_allocator
from iris.structures.event_script.containers import EVENT_BANK_LIMIT
from iris.structures.zone import Zone, move_all_zone_data, zone_data_pointer
from iris.tables import MapMetaObject


_VANILLA_ZONE_DATA_BYTES = 113877


def _blob(pointer: int) -> bytes:
    read_file.seek(pointer)
    length = int.from_bytes(read_file.read(2), "little")
    read_file.seek(pointer)
    return read_file.read(length)


def _pool_size() -> int:
    return sum(stop - start for start, stop in event_script_allocator._regions)  # noqa: SLF001


def test_every_blob_moves_unchanged() -> None:
    try:
        before = {index: _blob(zone_data_pointer(index)) for index in range(MapMetaObject.count)}
        move_all_zone_data()
        for index, blob in before.items():
            pointer = zone_data_pointer(index)
            assert pointer in ZONE_DATA_FREESPACE
            assert pointer & BANK_MASK == (pointer + len(blob) - 1) & BANK_MASK
            assert _blob(pointer) == blob
    finally:
        open_rom(original_file)


def test_the_old_bytes_become_the_event_pool() -> None:
    try:
        assert _pool_size() == 0
        move_all_zone_data()
        assert _pool_size() == _VANILLA_ZONE_DATA_BYTES
        assert all(stop <= EVENT_BANK_LIMIT for _, stop in event_script_allocator._regions)  # noqa: SLF001
    finally:
        open_rom(original_file)


def test_a_second_move_does_nothing() -> None:
    try:
        move_all_zone_data()
        image = output_bytes()
        move_all_zone_data()
        assert output_bytes() == image
        assert _pool_size() == _VANILLA_ZONE_DATA_BYTES
    finally:
        open_rom(original_file)


def test_zones_read_the_moved_blob() -> None:
    try:
        zone_data = Zone.from_index(0x10).data
        move_all_zone_data()
        assert zone_data.start == zone_data_pointer(0x10)
        assert Zone.from_index(0x11).data.start == zone_data_pointer(0x11)
    finally:
        open_rom(original_file)
