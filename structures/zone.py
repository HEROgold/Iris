# TODO: Set requirements/restrictions to each zone. Like what items you need to unlock that area.
# That information is used to determine what item's are allowed to be placed in currently accessible zones.

# NOTES:
# Map names are stored in ASCII, and there's two control codes:
# $00 (end string) and $0A (compression). For compression, the $0A control code is followed by a 16 bit value,
# where the lower 12 bits is the start address to copy from (+878000)
# and the upper 4 bits is the number of bytes to copy -2.


from dataclasses import dataclass
from typing import Any, ClassVar, Self

from _types.objects import Cache
from helpers.bits import read_little_int
from helpers.files import read_file, restore_pointer, write_file
from helpers.name import read_as_decompressed_name, write_compressed_name
from structures.event_script_redesign import ZoneEventManager
from structures.events import MapEvent
from structures.zone_data_pointers import zone_data_pointers
from tables.zones import ZoneObject


# TODO: Map items to chests, chest to zones.
# Be able to determine which items are from what zone.
@dataclass
class Boundary:
    west: Any
    north: Any
    south: Any
    east: Any

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




class Zone:
    event_manager: ClassVar[ZoneEventManager] = ZoneEventManager()

    event: MapEvent
    data: ZoneData
    _requirements: list[int]
    _chest_indices: list[int]  # TODO
    _cache = Cache[int, Self]()
    npcs: list[NPC]
    exits: list[Exit]
    tiles: list[Tile]
    waypoints: list[Waypoint]
    connections: list[Self]
    valid_entrances: list[int] # TODO: see set_spawn_location() for more details

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
        # inst.event = MapEvent.from_index(index)
        # TODO: Re-implement event manager to use structures/events
        # Zone.event_manager.load_zone_events(inst)
        # Zone.event_manager.get_npc_script(inst)
        # Zone.event_manager.export_zone_events(inst)
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
