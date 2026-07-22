# TODO: Set requirements/restrictions to each zone. Like what items you need to unlock that area.
# That information is used to determine what item's are allowed to be placed in currently accessible zones.

# NOTES:
# Map names are stored in ASCII, and there's two control codes:
# $00 (end string) and $0A (compression). For compression, the $0A control code is followed by a 16 bit value,
# where the lower 12 bits is the start address to copy from (+878000)
# and the upper 4 bits is the number of bytes to copy -2.


from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Self, SupportsIndex

from _types.objects import Cache
from constants import EMPTY_BYTES
from enums.event_scripts import EventClass
from helpers.addresses import address_to_lorom
from helpers.bits import read_little_int
from helpers.files import read_file, restore_pointer, write_file
from helpers.name import read_as_decompressed_name, write_compressed_name
from structures.event_script import EventScript, MapEvent, ZoneEventManager
from structures.zone_data_pointers import zone_data_pointers
from tables import MapMetaObject, ZoneObject


# The ROM table that locates each map's ZoneData: one 3-byte little-endian LoROM address per map index
# (see the lufia2-object-layout skill). Used to repoint a ZoneData blob after it is relocated.
ZONE_DATA_POINTER_TABLE = MapMetaObject.address
CHEST_SECTION = 18
SECTION_COUNT = 21
_free_cursor = EMPTY_BYTES[0].start  # simple bump allocator into the first freespace region


if TYPE_CHECKING:
    from structures.chest_location import ChestLocation


# TODO: Map items to chests, chest to zones.
# Be able to determine which items are from what zone.
@dataclass
class Boundary:
    west: SupportsIndex
    north: SupportsIndex
    south: SupportsIndex
    east: SupportsIndex

    def __bytes__(self) -> bytes:
        return bytes([self.west, self.north, self.south, self.east])


# TODO: differentiate between NPC and RoamingNPC
@dataclass
class NPC:
    index: int
    x: int
    y: int
    boundary: Boundary
    misc: int

    def __bytes__(self) -> bytes:
        return bytes([self.x, self.y, *bytes(self.boundary), self.misc])


@dataclass
class Exit:
    index: int
    boundary: Boundary
    misc: int
    destination_x: int
    destination_y: int
    destination_map: int

    def __bytes__(self) -> bytes:
        return bytes(
            [
                self.index,
                *bytes(self.boundary),
                self.misc,
                self.destination_x,
                self.destination_y,
                self.destination_map,
            ],
        )


@dataclass
class Tile:
    index: int
    boundary: Boundary

    def __bytes__(self) -> bytes:
        return bytes([self.index, *bytes(self.boundary)])


@dataclass
class Waypoint:
    index: int
    x: int
    y: int
    misc: int
    offsets: bytes

    def __bytes__(self) -> bytes:
        return bytes(
            [
                self.index,
                self.x,
                self.y,
                self.misc,
                *self.offsets,
            ],
        )


@dataclass
class Chest:
    """A chest's physical placement on a map (ZoneData section 18 record)."""

    slot_id: int  # per-map chest slot; usually 0,1,2,... but can skip on some maps
    x: int
    y: int
    chest_type: int  # small 1-4 value; chest sprite/type or a flag (usually constant per map)

    def __bytes__(self) -> bytes:
        return bytes([self.slot_id, self.x, self.y, self.chest_type])


class ZoneData:
    _cache = Cache[int, Self]()

    @restore_pointer
    def __init__(self, pointer: int) -> None:
        self.start = pointer
        read_file.seek(pointer)
        self.size = read_little_int(read_file, 2)
        self.data = read_file.read(self.size)
        self.parsed_data: dict[int, bytes] = {}

        self._parse_offsets()
        self._parse_npc_positions()
        self._parse_exits()
        self._parse_tiles()
        self._parse_waypoints()
        self._parse_chests()
        self._cache.to_cache(pointer, self)

    @classmethod
    def from_pointer(cls, pointer: int) -> Self:
        if inst := cls._cache.from_cache(pointer):
            return inst
        return cls(pointer)

    def _parse_waypoints(self) -> None:
        self.waypoints = []
        waypoint_data = self.parsed_data[8]
        if waypoint_data == b"\xff":
            return

        self.waypoints: list[Waypoint] = []
        while waypoint_data:
            if waypoint_data[0] == 0xff:
                break
            waypoint = Waypoint(
                waypoint_data[0],
                waypoint_data[1],
                waypoint_data[2],
                waypoint_data[3],
                waypoint_data[4:6],
            )
            waypoint_data = waypoint_data[6:]
            self.waypoints.append(waypoint)
        self.waypoint_shared_data = waypoint_data[1:] # Store the remaining data.

    def _parse_chests(self) -> None:
        """Parse section 18: the per-map chest-placement table (see docs/chest_system.md).

        Records are 4 bytes ``[slot_id, x, y, type]`` terminated by ``0xFF``. Parsed tolerantly: not
        every map has a clean chest table (section 18 matched chest counts on ~39/40 sampled maps), and
        ZoneData is built for *every* zone, so anything unexpected yields an empty list rather than an error.
        """
        data_size = 4
        chest_data = self.parsed_data[18]
        self.chests: list[Chest] = []
        if not chest_data or chest_data[-1] != 0xff or (len(chest_data) - 1) % data_size != 0:
            return

        for i in range(0, len(chest_data) - 1, data_size):
            self.chests.append(
                Chest(
                    chest_data[i + 0],
                    chest_data[i + 1],
                    chest_data[i + 2],
                    chest_data[i + 3],
                ),
            )

    def _parse_tiles(self) -> None:
        data_size = 5
        tile_data = self.parsed_data[5]
        data_length = len(tile_data)
        assert (data_length - 1) % data_size == 0
        assert tile_data[-1] == 0xff

        target = data_length - data_size
        self.tiles: list[Tile] = [
            Tile(
                tile_data[i+0],
                Boundary(*tile_data[i+1:i+5]),
            )
            for i in range(0, target, 5)
        ]


    def _parse_exits(self) -> None:
        data_size = 9
        exit_data = self.parsed_data[2]
        data_length = len(exit_data)
        assert (data_length-1) % data_size == 0
        assert exit_data[-1] == 0xff

        target = data_length - data_size # We count up, so we include the last data set
        self.exits: list[Exit] = [
            Exit(
                exit_data[i+0],
                Boundary(*exit_data[i+1:i+5]),
                exit_data[i+5],
                exit_data[i+6],
                exit_data[i+7],
                exit_data[i+9],
            )
            for i in range(0, target, data_size)
        ]

    def _parse_npc_positions(self) -> None:
        data_size = 8
        npc_position_data = self.parsed_data[7]
        data_length = len(npc_position_data)
        assert not (data_length-1) % data_size
        assert npc_position_data[-1] == 0xff

        target = data_length - data_size
        self.npc_positions: list[NPC] = [
            NPC(
                npc_position_data[i+0],
                npc_position_data[i+1],
                npc_position_data[i+2],
                Boundary(*npc_position_data[i+3:i+7]),
                npc_position_data[i+7],
            )
            for i in range(0, target, 8)
        ]


    def _parse_offsets(self) -> None:
        offsets: list[int] = [
            int.from_bytes(self.data[(i*2):(i*2)+2], "little")
            for i in range(21)
        ]
        clean_offsets = sorted(set(offsets))

        for i in range(21):
            offset = offsets[i]
            index = clean_offsets.index(offset)

            next_offset = self.size if index == len(clean_offsets) - 1 else clean_offsets[index + 1]
            assert offset < next_offset
            offset_data = self.data[offset-2:next_offset-2]
            if offset == 0x2C:
                assert offset_data == b"\xff"
            self.parsed_data[i] = offset_data

    def set_chests(self, chests: "list[Chest]") -> None:
        """Replace section 18 (the chest-placement table) with ``chests`` (0xFF-terminated)."""
        self.chests = list(chests)
        self.parsed_data[CHEST_SECTION] = b"".join(bytes(chest) for chest in chests) + b"\xff"

    def rebuild(self) -> bytes:
        """Reassemble the whole ZoneData blob from ``parsed_data`` (canonical layout).

        Empty sections (``b"\\xff"``) share offset ``0x2C`` (satisfying the parser's assert); every
        non-empty section gets its own offset, laid out in index order. Two pad bytes trail the last
        section for the parser's ``size-2`` end convention. The result parses back identically and is
        read by the game via the offset table (byte-for-byte identity with the original is NOT a goal).
        """
        empty = b"\xff"
        offsets = [0x2C] * SECTION_COUNT           # default: empty -> 0x2C (data index 42)
        body = bytearray(empty)                    # the shared empty marker at data index 42
        cursor = 43                                # data index of the first non-empty section
        for i in range(SECTION_COUNT):
            section = self.parsed_data[i]
            if section == empty:
                continue
            offsets[i] = cursor + 2                 # offset == data index + 2
            body += section
            cursor += len(section)
        body += b"\x00\x00"                         # pad for the last section's size-2 end
        offset_table = b"".join(offset.to_bytes(2, "little") for offset in offsets)
        data = offset_table + bytes(body)
        return len(data).to_bytes(2, "little") + data

    def write_relocated(self, map_index: int) -> None:
        """Rebuild this ZoneData, write it into free space, and repoint the map's pointer-table entry."""
        global _free_cursor  # noqa: PLW0603
        blob = self.rebuild()
        pointer = _free_cursor
        write_file.seek(pointer)
        write_file.write(blob)
        _free_cursor += len(blob)
        write_file.seek(ZONE_DATA_POINTER_TABLE + map_index * 3)
        write_file.write(address_to_lorom(pointer).to_bytes(3, "little"))
        self.start = pointer

    def write_section18_inplace(self) -> None:
        """Write section 18 back at its current location (only valid when its length is unchanged)."""
        offset18 = int.from_bytes(self.data[CHEST_SECTION * 2 : CHEST_SECTION * 2 + 2], "little")
        write_file.seek(self.start + offset18)
        write_file.write(self.parsed_data[CHEST_SECTION])




@dataclass(frozen=True)
class Entrance:
    """A valid way a new game can spawn the player into a map.

    Backed by a ``LOAD_MAP`` (A) event: ``cutscene`` is that event's index -- the ``entrance_cutscene``
    byte ``set_spawn_location`` writes (it runs the event, which loads the map graphics and positions the
    player). Frozen so it can live in a ``set``.
    """

    map_index: int
    cutscene: int


class Zone:
    event_manager: ClassVar[ZoneEventManager] = ZoneEventManager()

    event: MapEvent
    data: ZoneData
    _requirements: list[int]
    _chest_indices: list[int]
    _cache = Cache[int, Self]()
    npcs: list[NPC]
    exits: list[Exit]
    tiles: list[Tile]
    waypoints: list[Waypoint]
    connections: list[Self]

    @property
    def valid_entrances(self) -> set[Entrance]:
        """The entrances a new game can spawn the player at, for this map.

        Derived live from the map's ``LOAD_MAP`` (A) events: their indices are the only valid
        ``entrance_cutscene`` values (each runs an event that loads graphics + positions the player);
        any other yields a black screen. Computing it from the events (rather than a static list) keeps it
        correct when entrance scripts are added/edited for modding.
        """
        event = MapEvent.from_index(self.index)
        return {
            Entrance(self.index, script.index)
            for event_list in event.event_lists
            if event_list.event_class is EventClass.LOAD_MAP
            for script in event_list.events
        }

    def __init__(self, index: int, start: int, end: int) -> None:
        self._name = None
        self._modified_name = None  # Stores modified name before writing
        self._original_start = start  # Store original location for reference
        self.index = index
        self.start = start
        self.end = end
        self.npcs = []
        self.exits = []
        self.tiles = []
        self.waypoints = []
        self.connections = []

    def __repr__(self) -> str:
        return f"<Zone: {self.index}, {self.clean_name}>"

    @classmethod
    def from_index(cls, index: int) -> Self:
        if inst := cls._cache.from_cache(index):
            return inst
        # Generate this specific zone lazily
        cls._generate_zone(index)
        if inst := cls._cache.from_cache(index):
            return inst
        msg = f"Zone with index {index} could not be generated."
        raise IndexError(msg)

    @classmethod
    def from_name(cls, name: str) -> Self:
        if not cls._cache.values():
            cls._generate_zones()
        for zone in cls._cache.values():
            comparable_cname = zone.clean_name.decode().casefold()
            comparable_name = bytes(name, encoding="ascii").decode().casefold()
            if comparable_cname == comparable_name:
                return zone
        msg = f"Zone with name {name} not found."
        raise ValueError(msg)

    @classmethod
    def _find_zone_address(cls, target_index: int) -> tuple[int, int]:
        """Find the start and end address for a specific zone index.

        Args:
            target_index: The zone index to find the address for

        Returns:
            Tuple of (start_address, end_address)
        """
        # Start from the beginning of zone names
        current_address = ZoneObject.address

        # Iterate through zones up to the target
        for idx in range(target_index + 1):
            start_address = current_address

            # Read the compressed name to find where it ends
            read_file.seek(current_address)
            read_as_decompressed_name(current_address)
            end_address = read_file.tell()

            if idx == target_index:
                return (start_address, end_address)

            # Move to next zone's start
            current_address = end_address

        msg = f"Could not find address for zone {target_index}"
        raise ValueError(msg)

    @classmethod
    @restore_pointer
    def _generate_zone(cls, index: int) -> None:
        """Generate a single zone by index.

        Args:
            index: The zone index to generate
        """
        zone_data_count = len(zone_data_pointers)
        if index >= zone_data_count:
            msg = f"Zone index {index} out of range (max: {zone_data_count - 1})"
            raise IndexError(msg)

        # Check if already cached
        if cls._cache.from_cache(index):
            return

        # Find the correct address for this zone
        start_address, end_address = cls._find_zone_address(index)

        # Read the name
        read_file.seek(start_address)
        name = read_as_decompressed_name(start_address)

        # Create the zone instance
        inst = cls(index, start_address, end_address)
        inst._name = name
        inst.event = MapEvent.from_index(index)
        Zone.event_manager.load_zone_events(inst)
        # get_npc_script / export_zone_events are called on demand, not necessarily here.
        inst.data = ZoneData.from_pointer(zone_data_pointers[index])

        cls._cache.to_cache(index, inst)

    @classmethod
    def _generate_zones(cls) -> None:
        """Generate all zones (for backward compatibility)."""
        zone_data_count = len(zone_data_pointers)
        for idx in range(zone_data_count):
            if not cls._cache.from_cache(idx):
                cls._generate_zone(idx)

    @property
    def name(self):
        if self._name is None:
            self._name = read_as_decompressed_name(self.start)
        return self._name

    @name.setter
    def name(self, new_name: str | bytes) -> None:
        """Set a new name for the zone.

        Args:
            new_name: The new name as string or bytes. Will be converted to bytes if string.

        Note:
            The name change won't be written to ROM until write() is called.
            If the compressed name is longer than the original, freespace will be allocated.
        """
        if isinstance(new_name, str):
            new_name = new_name.encode("ascii")
        # Store the decompressed name for later writing
        self._modified_name = new_name
        # Update the cached name immediately so reads reflect the change
        self._name = new_name + b"\x00"

    @property
    def clean_name(self) -> bytes:
        # Remove the control byte for compressing
        return self.name.replace(b"\x0a", b"").replace(b"\x00", b"")

    @property
    def chests(self) -> "list[ChestLocation]":
        """The chests on this map, as ChestLocation hubs (sorted by global chest index).

        Realizes the intent of ``_chest_indices``: the chest->map mapping lives in the ported CHEST_MAP
        table, keyed by the same index as this zone. See ``structures.chest_location``.
        """
        from structures.chest_location import chests_by_map  # noqa: PLC0415  (avoid import cycle at load)

        located = chests_by_map().get(self.index, [])
        self._chest_indices = [location.chest_index for location in located]
        return located

    def referenced_script(self, index: int) -> EventScript:
        """Return this map's ``REFERENCED`` (talk) script with the given index.

        Talk scripts are the interactive scripts an NPC runs when talked to; a talk script's index
        equals the NPC slot (``0x50`` + npc index). Raises ``KeyError`` if no such script exists.
        """
        for event_list in self.event.event_lists:
            if event_list.event_class is EventClass.REFERENCED:
                for script in event_list.events:
                    if script.index == index:
                        return script
        msg = f"Zone {self.index}: no REFERENCED script with index {index:#04x}."
        raise KeyError(msg)

    def set_npc_sprite(self, slot: int, sprite_index: int) -> None:
        """Set the overworld sprite loaded for an NPC ``slot`` in this map's NPC-load script.

        Finds the ``0x68`` (load NPC) instruction for ``slot`` and repoints its sprite operand, marking
        the NPC-load script dirty so :meth:`write_events` persists it. Raises ``KeyError`` if the slot is
        not loaded by this map.
        """
        npc_script = self.event.npc_script
        for instruction in npc_script.instructions:
            if instruction.opcode == 0x68 and instruction.operands[0] == slot:
                instruction.operands[1] = sprite_index
                npc_script.dirty = True
                return
        msg = f"Zone {self.index}: NPC slot {slot:#04x} is not loaded (no 0x68 for it)."
        raise KeyError(msg)

    def write_events(self) -> None:
        """Persist this map's event scripts (only modified scripts are written)."""
        self.event.write()

    def write(self) -> None:
        """Write zone name to ROM.

        If the zone name has been modified via set_name(), this will:
        1. Check if the new compressed name fits in the original space
        2. If not, allocate new freespace for the name
        3. Write the compressed name to the appropriate location
        4. Update the zone's start pointer if relocated

        If the name hasn't been modified, writes back the original compressed bytes.
        """
        if self._modified_name is None:
            # Name not modified, write back original compressed bytes unchanged
            write_file.seek(self.start)
            compressed_name = self.read_compressed_name(self.start)
            write_file.seek(self.start)
            write_file.write(compressed_name)
            return

        # Name was modified, need to compress and check space
        from io import BytesIO


        # Calculate how much space the new compressed name will take
        # Write to a temporary buffer to measure size
        temp_buffer = BytesIO()
        original_pos = write_file.tell()

        # Temporarily redirect write_file to our buffer
        import helpers.files
        old_write_file = helpers.files.write_file
        helpers.files.write_file = temp_buffer

        try:
            write_compressed_name(0, self._modified_name)
            new_compressed_size = temp_buffer.tell()
            compressed_bytes = temp_buffer.getvalue()
        finally:
            # Restore original write_file
            helpers.files.write_file = old_write_file
            write_file.seek(original_pos)

        # Calculate available space at original location
        original_compressed = self.read_compressed_name(self.start)
        original_size = len(original_compressed)
        available_space = self.end - self.start

        if new_compressed_size <= available_space:
            # Fits in original location, write it there
            write_file.seek(self.start)
            write_file.write(compressed_bytes)
            # Pad with zeros if shorter than original to avoid leftover data
            if new_compressed_size < original_size:
                write_file.write(b"\x00" * (original_size - new_compressed_size))
        else:
            # Need to allocate new space
            # TODO: Implement freespace allocation
            # For now, write a warning and fall back to original location
            import logging

            from logger import iris
            log = logging.getLogger(f"{iris.name}.Zone")
            log.warning(
                f"Zone {self.index} '{self.clean_name.decode()}': "
                f"New compressed name size ({new_compressed_size} bytes) exceeds "
                f"available space ({available_space} bytes). "
                f"Freespace allocation not yet implemented. Name change may cause corruption!",
            )
            # Write anyway (will overwrite next zone!)
            write_file.seek(self.start)
            write_file.write(compressed_bytes)

        return

    @staticmethod
    def read_compressed_name(pointer: int) -> bytes:
        read_file.seek(pointer)
        name = b""
        while True:
            name += read_file.read(1)
            if name.endswith(b"\x00"):
                break
        return name

# Zones are now generated lazily on-demand via Zone.from_index()
# Call Zone._generate_zones() explicitly if you need to pre-load all zones

def generate_zones():
    for i in range(ZoneObject.count):
        yield Zone.from_index(i)
