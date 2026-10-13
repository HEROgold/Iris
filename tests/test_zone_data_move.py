"""``move_all_zone_data``: every map's ZoneData moves, unchanged, to the expansion area, and its old bytes in banks
$91-$94 become the event pool (the only room event containers can grow into, HER-232)."""

from collections.abc import Iterator

import pytest

from iris.constants import ZONE_DATA_FREESPACE
from iris.helpers import files
from iris.helpers.addresses import address_from_lorom
from iris.helpers.files import open_rom, original_file, output_bytes, read_file, session, use
from iris.helpers.freespace import BANK_MASK, event_script_allocator
from iris.structures.event_script.containers import EVENT_BANK_LIMIT
from iris.structures.zone import (
    ANCIENT_CAVE_ZONE_DATA_POINTER_COUNT,
    ANCIENT_CAVE_ZONE_DATA_POINTERS,
    Zone,
    move_all_zone_data,
    zone_data_pointer,
)
from iris.tables import MapMetaObject, select, selected


_VANILLA_ZONE_DATA_BYTES = 113877
_FINAL_FLOOR_BLOB = 0x0A6FE8
"""$94:EFE8: map 0xF1's (Ancient Cave Final Floor) ZoneData, the one Ancient Cave pointer target the move moves."""


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


@pytest.fixture
def restore() -> Iterator[None]:
    rom, patch = session(), selected()
    yield
    select(patch)
    use(rom)


def _blob_at(image: bytes, address: int) -> bytes:
    return image[address:address + int.from_bytes(image[address:address + 2], "little")]


def _ancient_cave_targets(image: bytes) -> list[int]:
    """Where the four Ancient Cave ZoneData pointers at $83:9F73 point (headerless offsets)."""
    sites = (ANCIENT_CAVE_ZONE_DATA_POINTERS + 3 * index for index in range(ANCIENT_CAVE_ZONE_DATA_POINTER_COUNT))
    return [address_from_lorom(int.from_bytes(image[site:site + 3], "little")) for site in sites]


@pytest.mark.parametrize("open_world", [False, True], ids=["linear", "open-world"])
@pytest.mark.usefixtures("restore")
def test_the_ancient_cave_pointers_follow_their_blob(open_world: bool) -> None:  # noqa: FBT001
    """Iris-Dev#69: map 0xF1's blob ($94:EFE8) moves, so its pointer follows; the other three blobs aren't in the
    pointer table, aren't moved and aren't given to the event pool, so their pointers stay."""
    pytest.importorskip("bsdiff4")
    from iris.build import build  # noqa: PLC0415
    from tools.build_ap_basepatch import OPEN_WORLD_OPTIONS, OPTIONS, vanilla_image  # noqa: PLC0415

    options = OPEN_WORLD_OPTIONS if open_world else OPTIONS
    vanilla = vanilla_image(files.original_file)
    image = build(vanilla, options)
    for old, new in zip(_ancient_cave_targets(vanilla), _ancient_cave_targets(image), strict=True):
        if old == _FINAL_FLOOR_BLOB:
            assert new >= EVENT_BANK_LIMIT
            assert new in ZONE_DATA_FREESPACE
        else:
            assert new == old
        assert _blob_at(image, new) == _blob_at(vanilla, old)
