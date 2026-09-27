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
from enums.event_scripts import EventClass
from helpers.addresses import address_to_lorom
from helpers.bits import read_little_int
from helpers.files import read_file, restore_pointer, write_file
from helpers.freespace import relocate_pointer_table_entry, zone_data_allocator
from helpers.name import compress_name, read_as_decompressed_name
from logger import iris
from structures.event_script import EventScript, MapEvent, ZoneEventManager
from structures.zone_data_pointers import zone_data_pointers
from tables import MapMetaObject, ZoneObject


# The ROM table that locates each map's ZoneData: one 3-byte little-endian LoROM address per map index
# (see the lufia2-object-layout skill). Used to repoint a ZoneData blob after it is relocated.
ZONE_DATA_POINTER_TABLE = MapMetaObject.address
EXIT_SECTION = 2
TILE_SECTION = 5
NPC_SECTION = 7
WAYPOINT_SECTION = 8
CHEST_SECTION = 18
SECTION_COUNT = 21


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
        return bytes([self.index, self.x, self.y, *bytes(self.boundary), self.misc])


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
        iris.debug(f"Creating ZoneData from {pointer=:#08x}")
        self.start = pointer
        read_file.seek(pointer)
        self.size = read_little_int(read_file, 2)
        self.data = read_file.read(self.size)
        self.parsed_data: dict[int, bytes] = {}
        self.dirty = False
        # True once write_relocated has moved this blob into the shared freespace pool -- only then
        # does its *previous* slot belong to that pool and need deallocating on the next relocation.
        self._relocated = False
        self._blob_length = self.size + 2  # the 2-byte size prefix + payload, as currently on ROM

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
        self.waypoints: list[Waypoint] = []
        self.waypoint_shared_data = b""
        self._waypoints_terminated = True
        waypoint_data = self.parsed_data[WAYPOINT_SECTION]
        if waypoint_data == b"\xff":
            return

        self._waypoints_terminated = False
        while waypoint_data:
            if waypoint_data[0] == 0xff:
                self._waypoints_terminated = True
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
        """Parse section 18: the per-map chest-placement table (see docs/guides/chests.md).

        Records are 4 bytes ``[slot_id, x, y, type]`` terminated by ``0xFF``. Parsed tolerantly: not
        every map has a clean chest table (section 18 matched chest counts on ~39/40 sampled maps), and
        ZoneData is built for *every* zone, so anything unexpected yields an empty list rather than an error.
        """
        data_size = 4
        chest_data = self.parsed_data[CHEST_SECTION]
        self.chests: list[Chest] = []
        # Only a cleanly parsed table is re-serialized from ``chests``; anything else is kept raw.
        self._chests_parsed = False
        if not chest_data or chest_data[-1] != 0xff or (len(chest_data) - 1) % data_size != 0:
            return

        self._chests_parsed = True
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
                exit_data[i+8],
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
        self._offsets = offsets
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
        self._chests_parsed = True
        self.dirty = True
        self.parsed_data[CHEST_SECTION] = b"".join(bytes(chest) for chest in chests) + b"\xff"

    def _sync_sections(self) -> None:
        """Re-serialize the decoded sections (exits, tiles, NPCs, waypoints, chests) into ``parsed_data``."""
        end = b"\xff"
        self.parsed_data[EXIT_SECTION] = b"".join(bytes(exit_) for exit_ in self.exits) + end
        self.parsed_data[TILE_SECTION] = b"".join(bytes(tile) for tile in self.tiles) + end
        self.parsed_data[NPC_SECTION] = b"".join(bytes(npc) for npc in self.npc_positions) + end
        waypoints = b"".join(bytes(waypoint) for waypoint in self.waypoints)
        if self._waypoints_terminated:
            waypoints += end + self.waypoint_shared_data
        self.parsed_data[WAYPOINT_SECTION] = waypoints
        if self._chests_parsed:
            self.parsed_data[CHEST_SECTION] = b"".join(bytes(chest) for chest in self.chests) + end

    def _layout_in_place(self) -> bytes | None:
        """The blob's payload with every section written back at its original offset.

        Returns ``None`` when a section changed length (or two sections sharing one offset diverged),
        i.e. when the blob can't be written back in place and needs :meth:`write_relocated`.
        """
        self._sync_sections()
        data = bytearray(self.data)
        written: dict[int, bytes] = {}
        for i, offset in enumerate(self._offsets):
            section = self.parsed_data[i]
            if offset in written:
                if written[offset] != section:
                    return None
                continue
            start = offset - 2
            original_end = min((other for other in self._offsets if other > offset), default=self.size) - 2
            if start + len(section) != original_end:
                return None
            data[start:original_end] = section
            written[offset] = section
        return bytes(data)

    def fits_in_place(self) -> bool:
        return self._layout_in_place() is not None

    def write(self) -> None:
        """Write this ZoneData back at ``self.start``, keeping the original offset table and layout.

        Only valid while every section keeps its original length; otherwise use :meth:`write_relocated`.
        """
        data = self._layout_in_place()
        if data is None:
            msg = f"ZoneData {self.start:#08x} no longer fits in place; use write_relocated."
            raise ValueError(msg)
        write_file.seek(self.start)
        write_file.write(self.size.to_bytes(2, "little"))
        write_file.write(data)

    def set_exits(self, exits: "list[Exit]") -> None:
        """Replace section 2 (the exit table) with ``exits`` (0xFF-terminated)."""
        self.exits = list(exits)
        self.dirty = True
        self.parsed_data[EXIT_SECTION] = b"".join(bytes(exit_) for exit_ in exits) + b"\xff"

    def set_npcs(self, npcs: "list[NPC]") -> None:
        """Replace section 7 (the NPC-position table) with ``npcs`` (0xFF-terminated)."""
        self.npc_positions = list(npcs)
        self.dirty = True
        self.parsed_data[NPC_SECTION] = b"".join(bytes(npc) for npc in npcs) + b"\xff"

    def rebuild(self) -> bytes:
        """Reassemble the whole ZoneData blob from ``parsed_data`` (canonical layout).

        Empty sections (``b"\\xff"``) share offset ``0x2C`` (satisfying the parser's assert); every
        non-empty section gets its own offset, laid out in index order. Two pad bytes trail the last
        section for the parser's ``size-2`` end convention. The result parses back identically and is
        read by the game via the offset table (byte-for-byte identity with the original is NOT a goal).
        """
        self._sync_sections()
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
        """Rebuild this ZoneData, write it into the shared freespace pool, and repoint the map's
        pointer-table entry.

        Deallocates this blob's *previous* slot first when it was itself an earlier relocation into
        this same pool -- the vanilla-original location is never part of the pool and is never
        deallocated.
        """
        blob = self.rebuild()
        if self._relocated:
            zone_data_allocator.deallocate(self.start, self._blob_length)
        pointer = zone_data_allocator.allocate(len(blob))
        zone_data_allocator.write(pointer, blob)
        relocate_pointer_table_entry(ZONE_DATA_POINTER_TABLE, map_index, 3, pointer, encode=address_to_lorom)
        self.start = pointer
        self.data = blob[2:]
        self.size = len(blob) - 2
        self._parse_offsets()  # the in-place layout check must see the new offset table
        self._blob_length = len(blob)
        self._relocated = True
        self.dirty = False
        # Re-register under the new pointer: from_pointer's cache is keyed by construction-time
        # pointer only, so without this a later ZoneData.from_pointer(pointer) (e.g. a second
        # MapMeta.write() on an already-relocated zone) would miss the cache and parse a second,
        # separate instance of the same blob instead of reusing this in-memory object.
        self._cache.to_cache(pointer, self)

    def write_section18_inplace(self) -> None:
        """Write section 18 back at its current location (only valid when its length is unchanged)."""
        offset18 = int.from_bytes(self.data[CHEST_SECTION * 2 : CHEST_SECTION * 2 + 2], "little")
        write_file.seek(self.start + offset18)
        write_file.write(self.parsed_data[CHEST_SECTION])
        self.dirty = False




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
        iris.debug(f"Creating Zone from {index=} ({start=:#08x}, {end=:#08x})")
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

        A name set through ``name`` is compressed for this zone's address and written over the old one, padded with
        spaces to the old length. A name that doesn't fit raises ``ValueError`` and writes nothing: moving a name
        elsewhere isn't supported yet.

        If the name hasn't been modified, writes back the original compressed bytes.
        """
        iris.debug(f"Writing Zone {self.index} name={self.clean_name.decode(errors='replace')!r} → start={self.start:#08x}")
        if self._modified_name is None:
            # Name not modified, write back original compressed bytes unchanged
            write_file.seek(self.start)
            compressed_name = self.read_compressed_name(self.start)
            write_file.seek(self.start)
            write_file.write(compressed_name)
            return

        # Encode at the zone's own address (back-references depend on it) without writing anything yet.
        compressed_bytes = compress_name(self.start, self._modified_name)
        available_space = self.end - self.start
        if len(compressed_bytes) > available_space:
            # TODO: place the name through rom_space and repoint the map's name pointer (HER-244 left this out).
            msg = (
                f"Zone {self.index}: compressed name {self._modified_name!r} needs {len(compressed_bytes)} bytes, "
                f"only {available_space} are free at {self.start:#x}."
            )
            raise ValueError(msg)
        # Names are packed back to back, and Zone._find_zone_address walks them terminator by terminator, so a
        # shorter name keeps its old span: pad with spaces before the terminator, not with extra 0x00 names.
        padding = b" " * (available_space - len(compressed_bytes))
        write_file.seek(self.start)
        write_file.write(compressed_bytes[:-1] + padding + compressed_bytes[-1:])

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
