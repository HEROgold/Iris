# TODO: Set requirements/restrictions to each zone. Like what items you need to unlock that area.
# That information is used to determine what item's are allowed to be placed in currently accessible zones.

# NOTES:
# Map names are stored in ASCII, and there's two control codes:
# $00 (end string) and $0A (compression). For compression, the $0A control code is followed by a 16 bit value,
# where the lower 12 bits is the start address to copy from (+878000) and the upper 4 bits is the number of bytes to copy -2.


from dataclasses import dataclass
from typing import Any, Self

from _types.objects import Cache
from helpers.bits import read_little_int
from helpers.files import read_file, write_file
from helpers.name import read_as_decompressed_name
from structures.events import MapEvent
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
    connections: list[Self]
    event: MapEvent
    data: ZoneData
    _requirements: list[int]
    _chest_indices: list[int]  # TODO
    _cache = Cache[int, Self]()

    def __init__(self, index: int, start: int, end: int) -> None:
        self._name = None
        self.index = index
        self.start = start
        self.end = end
        self.npcs: list[NPC] = []
        self.exits: list[Exit] = []
        self.tiles: list[Tile] = []
        self.waypoints: list[Waypoint] = []
        self.connections = []  # type: ignore[reportAttributeAccessIssue]

    def __repr__(self) -> str:
        return f"<Zone: {self.index}, {self.clean_name}>"

    @classmethod
    def from_index(cls, index: int) -> Self:
        if inst := cls._cache.from_cache(index):
            return inst
        cls._generate_zones()
        return cls.from_index(index)

    @classmethod
    def from_name(cls, name: str) -> Self:
        for zone in cls._cache.values():
            if zone.clean_name == bytes(name, encoding="ascii"):
                return zone
        cls._generate_zones()
        if zone := cls.from_name(name):
            return zone
        msg = f"Zone with name {name} not found."
        raise ValueError(msg)

    @classmethod
    def _generate_zones(cls) -> None:
        if len(cls._cache) >= 0xFF:
            msg = "All Zones already generated."
            raise ValueError(msg)
        current_index = 0
        start_address = 0
        prev_end_address = ZoneObject.address

        for idx in range(0xFF):
            read_file.seek(prev_end_address)
            start_address = read_file.tell()
            name = read_as_decompressed_name(start_address)
            prev_end_address = read_file.tell()

            inst = cls(current_index, start_address, prev_end_address)
            inst._name = name
            inst.event = MapEvent.from_index(idx)
            inst.data = ZoneData.from_pointer(zone_data_pointers[idx])

            cls._cache.to_cache(current_index, inst)
            current_index += 1

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
        read_as_decompressed_name(self.start)
        _compressed_name = self.read_compressed_name(self.start)
        # TODO: Implement
        # write_compressed_better(self.end, compressed_name)
        # write_as_compressed_name(self.end, self.name.decode("ascii"))
        # write_as_compressed_name(self.end, self.name.decode("ascii"))

    @staticmethod
    def read_compressed_name(pointer: int):
        read_file.seek(pointer)
        name = b""
        while True:
            name += read_file.read(1)
            if name.endswith(b"\x00"):
                break
        return name

zone_data_pointers = [
    0x90000,
    0xa6df1,
    0xa31ec,
    0x9bfbd,
    0x95bf8,
    0x8bda8,
    0x936ae,
    0xa0698,
    0xa2a7a,
    0xa539a,
    0x8d80b,
    0x98000,
    0x99066,
    0xa6b09,
    0xa63aa,
    0xa57c0,
    0x8b372,
    0x98724,
    0x9a478,
    0x95963,
    0x92b47,
    0xa4b7c,
    0xa5d35,
    0xa4097,
    0x933e0,
    0x9af3a,
    0x94c54,
    0x919af,
    0x8eaae,
    0xa30b9,
    0xa4d58,
    0xa27d4,
    0xa23c2,
    0xa0000,
    0x9bba3,
    0xa1505,
    0xa3e73,
    0xa1e17,
    0x9897c,
    0x9db55,
    0x9c5d7,
    0x9d787,
    0x9778b,
    0xa6300,
    0x8a807,
    0xa137b,
    0x93979,
    0x8d42d,
    0x972ab,
    0x8fc66,
    0x96b39,
    0x92298,
    0x92580,
    0xa6a8f,
    0xa644d,
    0x97ed2,
    0x9ea3d,
    0x97037,
    0x95190,
    0x9a6a2,
    0x9dd39,
    0x9f171,
    0xa3f87,
    0xa5474,
    0xa09dc,
    0xa1052,
    0x9df1d,
    0x9fa0c,
    0x9cfd1,
    0x8adf2,
    0x90362,
    0x9c9e0,
    0x91cad,
    0x8ee4c,
    0x9996a,
    0xa5eb6,
    0x956c8,
    0x968b9,
    0x9ad1e,
    0x92865,
    0xa38e6,
    0x9b152,
    0x979fa,
    0xa083a,
    0xa45bc,
    0xa4c6b,
    0xa3d5d,
    0xa6759,
    0x93109,
    0x994ee,
    0x9d1bf,
    0x94702,
    0x9a011,
    0xa42af,
    0x95e8c,
    0xa2d10,
    0xa292a,
    0x9aaf6,
    0x94ef3,
    0x92e28,
    0xa66c7,
    0x9b575,
    0xa0b7b,
    0xa5f75,
    0xa0d18,
    0x98269,
    0x9611d,
    0xa64f0,
    0xa6030,
    0x9fd64,
    0x9cddf,
    0x9d96f,
    0x9c7dc,
    0xa47af,
    0x93c36,
    0xa2523,
    0xa6a0b,
    0x9ec0c,
    0x9a246,
    0x8f8ed,
    0x8f56f,
    0xa658e,
    0x8cbeb,
    0xa01a9,
    0x9972c,
    0x99ba2,
    0xa2e4d,
    0xa5016,
    0x9b995,
    0x949ab,
    0xa3a08,
    0xa168e,
    0xa51df,
    0xa4a8a,
    0xa3b28,
    0xa20f9,
    0xa1f8c,
    0x91378,
    0xa369a,
    0xa56f0,
    0x96638,
    0x8df8a,
    0x8f1e6,
    0x8dbcd,
    0x8c28c,
    0xa43b7,
    0x8e6fd,
    0xa6b7d,
    0xa4e43,
    0x9f6b0,
    0xa1815,
    0xa11ee,
    0x984cb,
    0xa68fd,
    0xa37c1,
    0xa331e,
    0xa4f2e,
    0xa60e8,
    0xa6c57,
    0xa7035,
    0x8c748,
    0x98e1e,
    0x8d025,
    0x9542c,
    0x9f4fd,
    0xa2f84,
    0x98bcd,
    0xa67e7,
    0x9f33b,
    0x9bdb0,
    0x96db8,
    0xa1c9f,
    0x9f85e,
    0xa6252,
    0xa7079,
    0x909fd,
    0x99dda,
    0x906bb,
    0xa5aec,
    0x9e100,
    0x93ef1,
    0xa344a,
    0xa5a26,
    0xa6d8d,
    0x9cbe0,
    0x9c1c8,
    0x9d3ad,
    0x9b364,
    0x9b785,
    0x941a6,
    0xa267c,
    0xa48a4,
    0xa5c73,
    0x94455,
    0x91052,
    0x9c3d1,
    0x963ad,
    0xa6873,
    0xa5bb0,
    0x9fbb8,
    0xa6cc1,
    0xa6986,
    0xa3c45,
    0xa6bea,
    0x91fa7,
    0xa199b,
    0xa6ef2,
    0xa50fd,
    0xa61a0,
    0xa70bd,
    0x9e2dd,
    0x9169b,
    0x8e346,
    0x9a8cc,
    0x90d2a,
    0xa6f44,
    0xa41a6,
    0x9edd9,
    0x9e869,
    0xa225e,
    0xa46b9,
    0xa0eb5,
    0xa034f,
    0x9efa5,
    0xa44be,
    0x9e4ba,
    0xa04f4,
    0x97c67,
    0x9e692,
    0x992ac,
    0xa6e4c,
    0xa1b1e,
    0xa662c,
    0xa588e,
    0x9ff0f,
    0x9751b,
    0xa3572,
    0xa70fd,
    0xa6f96,
    0xa6d27,
    0xa2bc7,
    0xa6fe8,
    # 0x90000,    # Filler data for 243
    # 0x90000,    # Filler data for 244
    # 0x90000,    # Filler data for 245
    # 0x90000,    # Filler data for 246
    # 0x90000,    # Filler data for 247
    # 0x90000,    # Filler data for 248
    # 0x90000,    # Filler data for 249
    # 0x90000,    # Filler data for 250
    # 0x90000,    # Filler data for 251
    # 0x90000,    # Filler data for 252
    # 0x90000,    # Filler data for 253
    # 0x90000,    # Filler data for 254
    # 0x90000,    # Filler data for 255
]

def generate_zones():
    for i in range(ZoneObject.count):
        yield Zone.from_index(i)
