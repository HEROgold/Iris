
from dataclasses import dataclass
from textwrap import dedent

from helpers.files import BackupFile
from .properties import classproperty
from structures.todo.script import TableObject
from .map_events import MapEventObject
from helpers.addresses import address_from_lorom, address_to_lorom
from helpers.files import new_file
from logger import iris
from .names import Names

names = Names()


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


class NPCPosition:
    extra_event_signature: str | None
    sprite: str | None

    def __init__(self, index: int, x: int, y: int, boundary: Boundary, misc: int):
        self.index = index
        self.x = x
        self.y = y
        self.boundary = boundary
        self.misc = misc
        self._check_boundary()

    @classmethod
    def from_bytes(cls, data: bytes):
        assert len(data) == 8
        return cls(
            data[0],
            data[1],
            data[2],
            Boundary(
                data[3],
                data[4],
                data[5],
                data[6],
            ),
            data[7],
        )


    def _check_boundary(self):
        if {self.boundary.west, self.boundary.east,
                self.boundary.north, self.boundary.south} != {0xff}:
            try:
                assert self.boundary.west < self.boundary.east
                assert self.boundary.north < self.boundary.south
                if self.x != 0xff:
                    assert (self.boundary.west <= self.x
                            < self.boundary.east)
                if self.y != 0xff:
                    assert (self.boundary.north <= self.y
                            < self.boundary.south)
            except Exception:
                print(f'WARNING: NPC {self.index:x}, {self.x}, {self.y} has boundary errors.')

    def __repr__(self):
        if self.is_mobile:
            return (f'X:{self.boundary.west:0>2x}<={self.x:0>2x}<={self.boundary.east-1:0>2x} '
                    f'Y:{self.boundary.north:0>2x}<={self.y:0>2x}<={self.boundary.south-1:0>2x}')
        return f'X:{self.x:0>2x} Y:{self.y:0>2x}'

    @property
    def is_mobile(self):
        return (self.boundary.east - self.boundary.west > 1 or
                self.boundary.south - self.boundary.north > 1)

    @property
    def bytecode(self):
        return bytes([
            self.index,
            self.x,
            self.y,
            self.boundary.west,
            self.boundary.north,
            self.boundary.east,
            self.boundary.south,
            self.misc,
        ])


class Exit:
    def __init__(self, index: int, boundary: Boundary, misc: int, destination_x: int, destination_y: int, destination_map: int):
        self.index = index
        self.boundary = boundary
        self.misc = misc
        self.destination_x = destination_x
        self.destination_y = destination_y
        self.destination_map = destination_map

    @classmethod
    def from_bytes(cls, data: bytes):
        assert len(data) == 9
        return cls(
            data[0],
            Boundary(data[1], data[2], data[3], data[4]),
            data[5],
            data[6],
            data[7],
            data[8],
        )

    def __repr__(self):
        height = self.boundary.south - self.boundary.north
        width = self.boundary.east - self.boundary.west
        x = self.boundary.west
        y = self.boundary.north
        if self.destination_map == 0xff:
            destination_map = ''
        else:
            destination_map = f'{self.destination_map:0>2X} {MapEventObject.get(self.destination_map).name}'
        s = f'({x:0>2X},{y:0>2X}) -> {destination_map} ({self.destination_x:0>2X},{self.destination_y:0>2X})'
        if not height == width == 1:
            s = f'{s} {width}x{height}'
        while '  ' in s:
            s = s.replace('  ', ' ')
        return s

    @property
    def bytecode(self):
        return bytes([
            self.index,
            self.boundary.west,
            self.boundary.north,
            self.boundary.east,
            self.boundary.south,
            self.misc,
            self.destination_x,
            self.destination_y,
            self.destination_map,
        ])
        s = []
        for attr in ['index', 'boundary.west', 'boundary.north',
                        'boundary.east', 'boundary.south', 'misc',
                        'destination_x', 'destination_y', 'destination_map']:
            value = getattr(self, attr)
            s.append(value)
        return bytes(s)


class Tile:
    def __init__(self, index:int, boundary: Boundary):
        self.index = index
        self.boundary = boundary

    @classmethod
    def from_bytes(cls, data: bytes):
        assert len(data) == 5
        return cls(
            data[0],
            Boundary(data[1], data[2], data[3], data[4])
        )

    def __repr__(self):
        height = self.boundary.south - self.boundary.north
        width = self.boundary.east - self.boundary.west
        x = self.boundary.west
        y = self.boundary.north
        s = f'{x:0>2X},{y:0>2X}'
        if not height == width == 1:
            s = f'{s} {width}x{height}'
        return s

    @property
    def bytecode(self):
        return bytes([
            self.index,
            self.boundary.west,
            self.boundary.north,
            self.boundary.east,
            self.boundary.south,
        ])
        s = []
        for attr in ['index', 'boundary.west', 'boundary.north',
                        'boundary.east', 'boundary.south']:
            value = getattr(self, attr)
            s.append(value)
        return bytes(s)


class Waypoint:
    def __init__(self, index: int, x: int, y: int, misc: int, offset:int):
        self.index = index
        self.x = x
        self.y = y
        self.misc = misc
        self.offset = offset

    @classmethod
    def from_bytes(cls, data: bytes):
        assert len(data) == 6
        return cls(
            data[0],
            data[1],
            data[2],
            data[3],
            int.from_bytes(data[4:], byteorder='little')
        )

    def __repr__(self):
        return f'{self.index:0>2X} ({self.misc:0>2X}) {self.x:0>2X},{self.y:0>2X} {self.offset:0>4X}'

    @property
    def bytecode(self):
        s = bytes([self.index, self.x, self.y, self.misc])
        s += int.to_bytes(self.offset, byteorder='little', length=2)
        return s


class RoamingNPCObject(TableObject):
    # TODO: This is a placeholder for now
    every: list["RoamingNPCObject"] = []
    map_index: int
    map_npc_index: int
    sprite_index: int
    map_npc_event_index: int

    @property
    def sprite_name(self):
        return names.sprites[self.sprite_index]

class MapMetaObject(TableObject):
    free_space = [(0x3e8000, 0x3ec000)]
    ignore_exiting_data: set[tuple[int, int]] = set()

    def __init__(self, filename: str | None = None, pointer: int | None = None, index: int | None = None, groupindex: int = 0, size: int | None = None):
        # TODO: This is a placeholder for now
        super().__init__(filename, pointer, index, groupindex, size)

    @classproperty
    def after_order(self):
        return [MapEventObject]

    @property
    def name(self):
        return MapEventObject.get(self.index).name

    @property
    def pretty_positions(self):
        self.set_event_signatures()
        s = ''
        for npc_pos in self.npc_positions:
            event_signature = f'{self.index:0>2X}-C-{npc_pos.index + 0x4f:0>2X}'
            s += f'{npc_pos.index:0>2X} ({npc_pos.misc:0>2X}) {npc_pos} [{event_signature}]'
            if npc_pos.extra_event_signature:
                s += f' [{npc_pos.extra_event_signature}]'
            if npc_pos.sprite is not None:
                s += f' ROAMING {npc_pos.sprite}'
            s += '\n'
        return s.strip()

    @property
    def pretty_exits(self):
        s = ''
        for exit_ in self.exits:
            s += f'{exit_.index:0>2X} ({exit_.misc:0>2X}) {exit_}\n'
        return s.strip()

    @property
    def pretty_tiles(self):
        s = ''
        for tile in self.tiles:
            s += f'{tile.index:0>2X} {tile}\n'
        return s.strip()

    @property
    def roaming_npcs(self) -> list[RoamingNPCObject]:
        return [
            roaming_npc
            for roaming_npc in RoamingNPCObject.every
            if roaming_npc.map_index == self.index
        ]

    @property
    def bytecode(self):
        bytecode: dict[int, bytes] = {}
        npc_position_data = b''
        for npc_position in self.npc_positions:
            npc_position_data += npc_position.bytecode
        npc_position_data += b'\xff'
        bytecode[7] = npc_position_data

        exit_data = b''
        for my_exit in self.exits:
            exit_data += my_exit.bytecode
        exit_data += b'\xff'
        bytecode[2] = exit_data

        tile_data = b''
        for tile in self.tiles:
            tile_data += tile.bytecode
        tile_data += b'\xff'
        bytecode[5] = tile_data

        for i in self.old_bytecode:
            if i not in bytecode:
                bytecode[i] = self.old_bytecode[i]

        offset_order = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9,
                        11, 12, 13, 14, 15, 16, 17,
                        10, 19, 20, 18]

        offsets: dict[int, int] | list[int] = {}
        for i in sorted(bytecode):
            if i not in offset_order:
                assert bytecode[i] == b'\xff'
                offsets[i] = 0x2c

        bytestring = b'\xff'
        min_offset = 0
        for i in offset_order:
            if i == 8:
                waypoint_offset = len(bytestring) + 0x2c
                waypoint_offset += (6 * len(self.waypoints)) + 1
                waypoint_data = b''
                if self.waypoints:
                    min_offset = min([w.offset for w in self.waypoints])
                for waypoint in self.waypoints:
                    waypoint.offset += waypoint_offset - min_offset
                    waypoint_data += waypoint.bytecode
                waypoint_data += b'\xff' + self.waypoint_shared_data
                bytecode[8] = waypoint_data

            if i != 8 and bytecode[i] in bytestring and bytecode[i] == b'\xff':
                index = bytestring.index(bytecode[i])
            else:
                index = len(bytestring)
                bytestring += bytecode[i]

            index += 0x2c
            offsets[i] = index

        offsets = [offsets[i] for i in sorted(offsets)]
        assert len(offsets) == 21
        offset_str = b''.join([int.to_bytes(o, byteorder='little', length=2) for o in offsets])
        bytestring = offset_str + bytestring
        blocksize = int.to_bytes(len(bytestring) + 2, byteorder='little', length=2)
        bytestring = blocksize + bytestring

        # verify the stupid dumb waypoint data structure
        if self.waypoints:
            right = self.waypoints[0].offset
            left = right - 7
            check = self.waypoints[-1].bytecode + b'\xff'
            assert bytestring[left:right] == check
            right_right = right + len(self.waypoint_shared_data)
            assert bytestring[right:right_right] == self.waypoint_shared_data

        return bytestring

    def get_next_npc_index(self):
        if self.npc_positions:
            index = max(npc_pos.index for npc_pos in self.npc_positions) + 1
        else:
            index = 1
        return index

    def get_next_exit_index(self):
        if self.exits:
            index = max(x.index for x in self.exits) + 1
        else:
            index = 0
        return index

    def add_npc(self, x: int | None, y: int | None, boundary: Boundary | None=None, misc: int=0, force_index: int | None=None):
        assert x is not None
        assert y is not None
        assert boundary is not None
        boundary.east += 1
        boundary.south += 1
        assert boundary.east > boundary.west
        assert boundary.south > boundary.north
        index = self.get_forced_index(force_index)
        assert 1 <= index <= 0x20
        npc_pos = NPCPosition(index, x, y, boundary, misc)
        self.npc_positions.append(npc_pos)
        self.npc_positions = sorted(self.npc_positions, key=lambda x: x.index)  # FIXME: sorting takes time, do we need this?
        return npc_pos

    def get_forced_index(self, force_index: int | None):
        if force_index:
            index = force_index
        else:
            index = self.get_next_npc_index()
        return index

    def add_exit(
        self,
        boundary: Boundary,
        destination_map: int,
        destination_x: int,
        destination_y: int,
        misc: int = 0xF0,
        force_index: int | None = None,
    ):
        if destination_map == self.index:
            destination_map = 0xFF
        boundary.east += 1
        boundary.south += 1
        assert boundary.east > boundary.west
        assert boundary.south > boundary.north
        index = self.get_forced_index(force_index)
        my_exit = Exit(
            index,
            boundary,
            misc,
            destination_x,
            destination_y,
            destination_map,
        )
        self.exits.append(my_exit)
        self.exits = sorted(self.exits, key=lambda x: x.index)
        return my_exit

    def add_tile(self, boundary: Boundary, index: int):
        tile = Tile(index, boundary)
        self.tiles.append(tile)
        self.tiles = sorted(self.tiles, key=lambda t: t.index)

    def add_or_replace_npc(
        self,
        x: int,
        y: int,
        boundary: Boundary | None = None,
        misc: int = 0,
        index: int | None = None,
    ) -> NPCPosition:
        if index is None:
            return self.add_npc(x, y, boundary, misc)

        existing = [npc_pos for npc_pos in self.npc_positions if npc_pos.index == index]
        if existing:
            assert len(existing) == 1
            self.npc_positions.remove(existing[0])
        return self.add_npc(x, y, boundary, misc, force_index=index)

    def add_or_replace_exit(
        self,
        boundary: Boundary,
        destination_map: int,
        destination_x: int,
        destination_y: int,
        misc: int = 0xF0,
        index: int | None = None,
    ) -> Exit:
        if index is None:
            return self.add_exit(boundary, destination_map, destination_x, destination_y, misc)
        existing = [x for x in self.exits if x.index == index]
        if existing:
            assert len(existing) == 1
            self.exits.remove(existing[0])
        return self.add_exit(
            boundary,
            destination_map,
            destination_x,
            destination_y,
            misc,
            force_index=index,
        )

    def add_or_replace_tile(self, boundary: Boundary, index: int):
        existing = [t for t in self.tiles if t.index == index]
        if existing:
            assert len(existing) == 1
            self.tiles.remove(existing[0])
        return self.add_tile(boundary, index=index)

    def set_event_signatures(self):
        for npc_pos in self.npc_positions:
            extra_matches = [
                roaming_npc
                for roaming_npc in self.roaming_npcs
                if roaming_npc.map_npc_index == npc_pos.index
            ]
            if extra_matches:
                assert len(extra_matches) == 1
                extra = extra_matches[0]
                sprite_index = extra.sprite_index
                map_npc_event_index = extra.map_npc_event_index
                event_signature = f'{self.index:0>2X}-C-{map_npc_event_index:0>2X}'
                sprite = f'{extra.map_npc_event_index:0>2x} {names.sprites[sprite_index]}'
                npc_pos.extra_event_signature = event_signature
                npc_pos.sprite = sprite
            else:
                npc_pos.extra_event_signature = None
                npc_pos.sprite = None

    def get_npc_position_by_index(self, index: int):
        npc_pos = [npc_pos for npc_pos in self.npc_positions if npc_pos.index == index]
        if len(npc_pos) != 1:
            return None
        return npc_pos[0]

    def read_data(self, filename: str | None=None, pointer: int | None=None):
        super().read_data(filename, pointer)

        with BackupFile(new_file) as backup, backup.open("wb+") as f:
            pointer = address_from_lorom(self.reference_pointer)
            f.seek(pointer)
            blocksize = int.from_bytes(f.read(2), byteorder='little')
            f.seek(pointer)
            data = f.read(blocksize)
            self.deallocate((pointer, pointer+blocksize))
            self.old_bytecode: dict[int, bytes] = {}

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
            self.old_bytecode[i] = offset_data

        self.npc_positions: list[NPCPosition] = []
        npc_position_data = self.old_bytecode[7]
        assert not (len(npc_position_data)-1) % 8
        assert npc_position_data[-1] == 0xff
        npc_position_data = npc_position_data[:-1]
        while npc_position_data:
            npc_position = NPCPosition.from_bytes(npc_position_data[:8])
            npc_position_data = npc_position_data[8:]
            self.npc_positions.append(npc_position)
        self.old_num_npcs = len(self.npc_positions)

        self.exits: list[Exit] = []
        exit_data = self.old_bytecode[2]
        assert not (len(exit_data)-1) % 9
        assert exit_data[-1] == 0xff
        exit_data = exit_data[:-1]
        while exit_data:
            my_exit = Exit.from_bytes(exit_data[:9])
            exit_data = exit_data[9:]
            self.exits.append(my_exit)
        self.old_num_exits = len(self.exits)

        self.tiles: list[Tile] = []
        tile_data = self.old_bytecode[5]
        assert not (len(tile_data)-1) % 5
        assert tile_data[-1] == 0xff
        tile_data = tile_data[:-1]
        while tile_data:
            tile = Tile.from_bytes(tile_data[:5])
            tile_data = tile_data[5:]
            self.tiles.append(tile)
        self.old_num_tiles = len(self.tiles)

        self.waypoints: list[Waypoint] = []
        waypoint_data = self.old_bytecode[8]
        while waypoint_data:
            if waypoint_data[0] == 0xff:
                break
            waypoint = Waypoint.from_bytes(waypoint_data[:6])
            waypoint_data = waypoint_data[6:]
            self.waypoints.append(waypoint)
        self.waypoint_shared_data = waypoint_data[1:]

    def cleanup(self):
        npc_pos_indexes = [npc_pos.index for npc_pos in self.npc_positions]
        assert len(npc_pos_indexes) == len(set(npc_pos_indexes))

    @classmethod
    def full_cleanup(cls):
        cls.separate_free_space_banks()
        super().full_cleanup()

    @classmethod
    def deallocate(cls, to_deallocate: tuple[int, int] | set[tuple[int, int]]):
        if isinstance(to_deallocate, tuple):
            to_deallocate = {to_deallocate}
        old_free_space = set(cls.free_space)
        temp = sorted(set(cls.free_space) | to_deallocate)
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

        cls.free_space = sorted(temp)
        cls.ignore_exiting_data |= (set(cls.free_space) - old_free_space)

    @classmethod
    def separate_free_space_banks(cls):
        with BackupFile(new_file) as backup, backup.open("rb") as f:
            free_space = []
            for (a, b) in cls.free_space:
                assert b > a
                if not any(
                    a >= a2 and b <= b2
                    for (a2, b2) in cls.ignore_exiting_data
                ):
                    f.seek(a)
                    old_data = f.read(b-a)
                    if tuple(set(old_data)) not in {(0,), (0xff,)}:
                        msg = dedent(f'''
                            WARNING: Address range {a:0>6X}-{b:0>6X} 
                            designated as free space, but appears to 
                            be occupied.''')
                        iris.warning(msg)
                while (b & 0xFF8000) > (a & 0xFF8000):
                    new_a = (a & 0xFF8000) + 0x8000
                    free_space.append((a, new_a))
                    a = new_a
                free_space.append((a, b))
            cls.free_space = free_space

    def write_data(self, filename: str | None=None, pointer: int | None=None, syncing: bool=False):
        blocksize = len(self.bytecode)
        candidates = sorted([
                (a, b) for (a, b) in MapMetaObject.free_space
                if b-a >= blocksize
            ],
            key=lambda x: x[1]-x[0]
        )
        lower, upper = candidates[0]
        MapMetaObject.free_space.remove((lower, upper))
        assert lower+blocksize <= upper
        MapMetaObject.free_space.append((lower+blocksize, upper))
        with BackupFile(new_file) as backup, backup.open("r+b") as f:
            f.seek(lower)
            f.write(self.bytecode)
            self.reference_pointer = address_to_lorom(lower)
            super().write_data(filename, pointer)
