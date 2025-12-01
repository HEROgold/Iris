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
from helpers.files import read_file, write_file
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

    def __init__(self, index: int, start: int, end: int) -> None:
        self._name = None
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
        return cls.from_index(index)

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
    def _generate_zones(cls) -> None:
        zone_data_count = len(zone_data_pointers)
        if len(cls._cache) >= zone_data_count:
            msg = "All Zones already generated."
            raise ValueError(msg)
        start_address = 0
        prev_end_address = ZoneObject.address

        for current_index, idx in enumerate(range(zone_data_count)):
            read_file.seek(prev_end_address)
            start_address = read_file.tell()
            name = read_as_decompressed_name(start_address)
            prev_end_address = read_file.tell()

            inst = cls(current_index, start_address, prev_end_address)
            inst._name = name
            inst.event = MapEvent.from_index(idx)
            Zone.event_manager.load_zone_events(inst)
            Zone.event_manager.get_npc_script(inst)
            Zone.event_manager.export_zone_events(inst)
            inst.data = ZoneData.from_pointer(zone_data_pointers[idx])

            cls._cache.to_cache(current_index, inst)

    @property
    def name(self):
        if self._name is None:
            self._name = read_as_decompressed_name(self.start)
        return self._name

    @property
    def clean_name(self) -> bytes:
        # Remove the control byte for compressing
        return self.name.replace(b"\x0a", b"").replace(b"\x00", b"")

    def write(self) -> None:
        write_file.seek(self.start)
        _compressed_name1 = read_as_decompressed_name(self.start)
        _compressed_name2 = self.read_compressed_name(self.start)
        # assert _compressed_name1 == _compressed_name2, "Compressed name read methods do not match!"
        write_compressed_name(self.start, _compressed_name1)
        return

    @staticmethod
    def read_compressed_name(pointer: int):
        read_file.seek(pointer)
        name = b""
        while True:
            name += read_file.read(1)
            if name.endswith(b"\x00"):
                break
        return name

Zone._generate_zones()  # type: ignore[reportPrivateUsage] # Generate all zones on import.  # noqa: SLF001

def generate_zones():
    for i in range(ZoneObject.count):
        yield Zone.from_index(i)
