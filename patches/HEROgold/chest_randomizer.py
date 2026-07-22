"""Two independent chest randomizers, built on the chest model in ``structures/chest*``.

- :func:`randomize_chest_contents` -- change WHAT each chest holds (the item). Positions are untouched,
  so the content<->position link is preserved. Uses the fixed ``PointerChest``/``AddressChest`` writers.
- :func:`randomize_chest_locations` -- change WHERE each chest sits, *within its own map*, by permuting
  the ``(x, y)`` of that map's chests in the map's ``ZoneData`` section 18 (see ``docs/chest_system.md``
  / ``info/L2_ChestData.txt``). This is a same-length, in-place edit, so no ZoneData reassembler is
  needed and every chest stays on an already-valid tile. Cross-map relocation is intentionally NOT done
  here: it needs a ZoneData reassembler, the confirmed content<->slot linkage, and collision data.

Both use the global ``read_file``/``write_file`` handles, like every other patch.
"""

import logging
import random

from helpers.files import write_file
from logger import iris
from structures.chest import AddressChest, PointerChest
from structures.chest_location import chests_by_map
from structures.item import Item
from structures.zone import Zone
from tables import AncientChest1Object, AncientChest2Object, BlueChestObject, ChestObject


log = logging.getLogger(f"{iris.name}.ChestRandomizer")

MAX_ITEM_INDEX = 0x1D2  # 466 -- highest normal item index (matches HEROgold's existing range)
CHEST_RECORD_SIZE = 4   # ZoneData section 18 record: [slot_id, x, y, type]
SECTION_COUNT = 21


def _content_chests() -> list[PointerChest | AddressChest]:
    """Every chest whose *contents* are writable: normal (red) + Blue/Ancient."""
    chests: list[PointerChest | AddressChest] = [PointerChest.from_pointer(p) for p in ChestObject.pointers]
    for table in (BlueChestObject, AncientChest1Object, AncientChest2Object):
        chests += [AddressChest.from_table(table.address, index) for index in range(table.count)]
    return chests


def randomize_chest_contents() -> None:
    """Give every chest a random item. (Contents only; chest positions are left where they are.)"""
    iris.info("Randomizing chest contents.")
    for chest in _content_chests():
        chest.item = Item.from_index(random.randint(0, MAX_ITEM_INDEX))
        chest.write()


def _section18_file_offset(zone: Zone) -> int:
    """File offset of a map's ZoneData section 18 (the chest-placement table)."""
    data = zone.data
    offset_18 = int.from_bytes(data.data[18 * 2 : 18 * 2 + 2], "little")
    return data.start + offset_18


def randomize_chest_locations() -> None:
    """Shuffle chest positions within each map (permutes ``(x, y)`` among a map's own chests).

    Same-length, in-place edit of ZoneData section 18 -- every chest keeps its slot/type and moves to
    another of that map's existing (valid) chest tiles, so the item that was at one spot now appears at
    another. Maps with fewer than two chests are skipped (nothing to shuffle).
    """
    iris.info("Randomizing chest locations (within each map).")
    for map_index, chests in chests_by_map().items():
        if len(chests) < 2:
            continue
        try:
            zone = Zone.from_index(map_index)
        except Exception:  # noqa: BLE001
            log.warning("Map %#04x: could not load zone; skipping chest-location shuffle.", map_index)
            continue

        raw = zone.data.parsed_data[18]
        if not raw or raw[-1] != 0xFF or (len(raw) - 1) % CHEST_RECORD_SIZE != 0:
            log.warning("Map %#04x: unexpected section-18 layout (%d bytes); skipping.", map_index, len(raw))
            continue

        records = [bytearray(raw[i : i + CHEST_RECORD_SIZE]) for i in range(0, len(raw) - 1, CHEST_RECORD_SIZE)]
        positions = [(record[1], record[2]) for record in records]
        random.shuffle(positions)
        for record, (x, y) in zip(records, positions, strict=True):
            record[1], record[2] = x, y

        new = b"".join(bytes(record) for record in records) + b"\xff"
        if len(new) != len(raw):
            log.warning("Map %#04x: rebuilt section 18 changed length; skipping.", map_index)
            continue

        write_file.seek(_section18_file_offset(zone))
        write_file.write(new)
