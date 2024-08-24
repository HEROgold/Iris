

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Self

from _types.objects import Cache
from helpers.addresses import address_from_lorom
from helpers.files import BackupFile, new_file, read_file


@dataclass
class Boundary:
    def __init__(self, west: int, north: int, east: int, south: int) -> None:
        self.west = west
        self.north = north
        self.east = east
        self.south = south

    def __repr__(self) -> str:
        return f"{self.west}, {self.north}, {self.east}, {self.south}"
    
    @property
    def bytecode(self) -> bytes:
        return bytes([self.west, self.north, self.east, self.south])

@dataclass
class Destination:
    def __init__(self, x: int, y: int, map: int) -> None:
        self.x = x
        self.y = y
        self.map = map

    def __repr__(self) -> str:
        return f"<Destination {self.x}, {self.y}, {self.map}>"

    @property
    def bytecode(self) -> bytes:
        return bytes([self.x, self.y, self.map])

@dataclass
class Tile:
    def __init__(self, index: int, boundary: Boundary):
        self.index = index
        self.boundary = boundary

    def __repr__(self):
        return f"<Tile {self.index}>"

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        index, west, north, east, south = data
        return cls(index, Boundary(west, north, east, south))

    @property
    def bytecode(self):
        return bytes([self.index]) + self.boundary.bytecode

@dataclass
class Waypoint:
    def __init__(self, index: int, x: int, y: int, misc: int, offset: int):
        self.index = index
        self.x = x
        self.y = y
        self.misc = misc
        self.offset = offset

    def __repr__(self):
        return F"<Waypoint {self.index}, {self.x}, {self.y}, {self.offset}, {self.misc}>"

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        index, x, y, misc = data
        offset = int.from_bytes(data[4:6], byteorder='little')
        return cls(index, x, y, misc, offset)

    @property
    def bytecode(self):
        return bytes([self.index, self.x, self.y, self.misc]) + int.to_bytes(self.offset, byteorder='little', length=2)

@dataclass
class NPCPosition:
    def __init__(self, index: int, x: int, y: int, boundary: Boundary, misc: int):
        self.index = index
        self.x = x
        self.y = y
        self.boundary = boundary
        self.misc = misc

        if {self.boundary.west, self.boundary.east, self.boundary.north, self.boundary.south} != {0xff}:
            assert self.boundary.west < self.boundary.east
            assert self.boundary.north < self.boundary.south
            if self.x != 0xff:
                assert (self.boundary.west <= self.x < self.boundary.east)
            if self.y != 0xff:
                assert (self.boundary.north <= self.y < self.boundary.south)

    def __repr__(self):
        return f"<NPCPosition {self.is_mobile=} {self.index}, {self.x}, {self.y}, {self.boundary}, {self.misc}>"

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        index, x, y, west, north, east, south, misc = data
        return cls(index, x, y, Boundary(west, north, east, south), misc)

    @property
    def is_mobile(self):
        return (
            self.boundary.east - self.boundary.west > 1 or
            self.boundary.south - self.boundary.north > 1
        )

    @property
    def bytecode(self):
        return bytes([self.index, self.x, self.y]) + self.boundary.bytecode + bytes([self.misc])


class Label:
    pass

class Instruction:
    pass

class Event:
    pass

class Exit:
    def __init__(self, index: int, boundary: Boundary, misc: int, destination: Destination) -> None:
        self.index = index
        self.boundary = boundary
        self.misc = misc
        self.destination = destination

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        index, west, north, east, south, misc, x, y, map = data
        return cls(index, Boundary(west, north, east, south), misc, Destination(x, y, map))


class MapEvent:
    cache = Cache[int, Self]()
    empty_space: list[tuple[int, int]] = [(0x3e8000, 0x3ec000)]
    ignore_exiting_data: set[tuple[int, int]] = set()

    old_bytecode: dict[int, bytes] = {}
    npc_positions: dict[int, NPCPosition] = {}
    exits: dict[int, Exit] = {}
    tiles: dict[int, Tile] = {}
    waypoints: dict[int, Waypoint] = {}
    event_lists: dict[str, Any] = {}
    waypoint_shared_data: bytes = b""


    def __init__(self, index: int, pointer: int, name: str) -> None:
        self.index = index
        self.pointer = pointer
        self.name = name

    def __repr__(self) -> str:
        return f"MapEvent({self.index=}, {self.pointer=}, {self.name=})"

    @classmethod
    def deallocate(cls, to_deallocate: list[tuple[int, int]]):
        old_free_space = set(cls.empty_space)
        temp = sorted(set(cls.empty_space) | set(to_deallocate))
        while True:
            temp = sorted(temp)
            for ((a1, b1), (a2, b2)) in zip(temp, temp[1:]):
                assert a1 <= a2
                assert a1 < b1
                assert a2 < b2
                if a1 <= a2 <= b1:
                    temp.remove((a1, b1))
                    temp.remove((a2, b2))
                    temp.append((min(a1, a2), max(b1, b2)))
                    break
            else:
                break

        cls.empty_space = sorted(temp)
        cls.ignore_exiting_data |= (set(cls.empty_space) - old_free_space)

    @classmethod
    def from_index(cls, index: int) -> Self:
        # TODO: get pointer from index, or use cache.
        return cls.from_pointer()

    @classmethod
    def from_pointer(cls, pointer: int):
        with BackupFile(new_file) as backup, backup.open("wb+") as f:
            f.seek(pointer)
            blocksize = int.from_bytes(f.read(2), byteorder='little')
            f.seek(pointer)
            data = f.read(blocksize)
            cls.deallocate([(pointer, pointer+blocksize)])

        offsets: list[int] = []
        for i in range(21):
            i *= 2
            offset = int.from_bytes(data[i+2:i+4], byteorder='little')
            offsets.append(offset)
        sorted_offsets = sorted(set(offsets))

        for i in range(21):
            offset = offsets[i]
            offset_index = sorted_offsets.index(offset)
            if offset_index == len(sorted_offsets)-1:
                next_offset = blocksize
            else:
                next_offset = sorted_offsets[offset_index+1]
            assert next_offset > offset
            offset_data = data[offset:next_offset]
            if offset == 0x2c:
                assert offset_data == b'\xff'
            cls.old_bytecode[i] = offset_data

        npc_position_data = cls.old_bytecode[7]
        assert not (len(npc_position_data)-1) % 8
        assert npc_position_data[-1] == 0xff
        npc_position_data = npc_position_data[:-1]
        while npc_position_data:
            npc_position = NPCPosition.from_bytes(npc_position_data[:8])
            cls.npc_positions[npc_position.index] = npc_position
            npc_position_data = npc_position_data[8:]
        cls.old_num_npcs = len(cls.npc_positions)

        exit_data = cls.old_bytecode[2]
        assert not (len(exit_data)-1) % 9
        assert exit_data[-1] == 0xff
        exit_data = exit_data[:-1]
        while exit_data:
            exit = Exit.from_bytes(exit_data[:9])
            cls.exits[exit.index] = exit
            exit_data = exit_data[9:]
        cls.old_num_exits = len(cls.exits)

        tile_data = cls.old_bytecode[5]
        assert not (len(tile_data)-1) % 5
        assert tile_data[-1] == 0xff
        tile_data = tile_data[:-1]
        while tile_data:
            tile = Tile.from_bytes(tile_data[:5])
            cls.tiles[tile.index] = tile
            tile_data = tile_data[5:]
        cls.old_num_tiles = len(cls.tiles)

        waypoint_data = cls.old_bytecode[8]
        while waypoint_data:
            if waypoint_data[0] == 0xff:
                break
            waypoint = Waypoint.from_bytes(waypoint_data[:6])
            cls.waypoints[waypoint.index] = waypoint
            waypoint_data = waypoint_data[6:]
        cls.waypoint_shared_data = waypoint_data[1:]

    def set_npc(self, npc: NPCPosition):
        self.npc_positions[npc.index] = npc

    def set_exit(self, exit: Exit):
        self.exits[exit.index] = exit

    def set_tile(self, tile: Tile):
        self.tiles[tile.index] = tile
