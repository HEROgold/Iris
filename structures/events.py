from helpers.files import read_file
from typing import Self
from abc_.pointers import AddressPointer
from helpers.bits import read_little_int
from tables import MapEventObject

# Structure
# class EventInstObject:
#     reference_pointer = 2
#     address = 0x4A14
#     count = 205


class Event(AddressPointer):
    def __init__(self, op_code: bytes, args: bytes) -> None:
        self.op_code = op_code
        self.args = args

    def __repr__(self) -> str:
        return f" {self.op_code} > {self.args}"



MAP_EVENT_SIZE = sum(
    [
        MapEventObject.eventlist_lowbytes,
        MapEventObject.eventlist_highbyte,
        MapEventObject.npc_lowbytes,
        MapEventObject.npc_highbyte,
        MapEventObject.map_name_pointer,
    ]
)


class MapEvent(AddressPointer):
    def __init__(
        self,
        map_name_pointer: int,
        low_byte: int,
        high_byte: int,
        npc_low_byte: int,
        npc_high_byte: int,
    ) -> None:
        self.map_name_pointer = map_name_pointer
        self.low_byte = low_byte
        self.high_byte = high_byte
        self.npc_low_byte = npc_low_byte
        self.npc_high_byte = npc_high_byte

    @classmethod
    def from_table(cls, address: int, index: int) -> Self:
        read_file.seek(address + index * MAP_EVENT_SIZE, 0)
        inst = cls(
            read_little_int(read_file, MapEventObject.map_name_pointer),
            read_little_int(read_file, MapEventObject.eventlist_lowbytes),
            read_little_int(read_file, MapEventObject.eventlist_highbyte),
            read_little_int(read_file, MapEventObject.npc_lowbytes),
            read_little_int(read_file, MapEventObject.npc_highbyte),
        )
        super().__init__(inst, address, index)
        return inst


