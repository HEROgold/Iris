from helpers.files import read_file, restore_pointer, write_file
from typing import Self
from helpers.bits import read_little_int
from tables import RoamingNPCObject
from abc_.pointers import ReferencePointer

NPC_SIZE = sum(
    [
        RoamingNPCObject.map_npc_event_index,
        RoamingNPCObject.sprite_index,
        RoamingNPCObject.map_index,
        RoamingNPCObject.map_npc_index,
    ]
)

class RoamingNPC(ReferencePointer):
    def __init__(
        self,
        npc_event_map_index: int,
        sprite_index: int,
        map_index: int,
        map_npc_index: int,
    ) -> None:
        self.npc_event_map_index = npc_event_map_index
        self.sprite_index = sprite_index
        self.map_index = map_index
        self.map_npc_index = map_npc_index

    @classmethod
    @restore_pointer
    def from_reference(cls, address: int, index: int, size: int) -> Self:
        read_file.seek(address + index * size)
        inst = cls(
            npc_event_map_index=read_little_int(read_file, RoamingNPCObject.map_npc_event_index),
            sprite_index=read_little_int(read_file, RoamingNPCObject.sprite_index),
            map_index=read_little_int(read_file, RoamingNPCObject.map_index),
            map_npc_index=read_little_int(read_file, size=RoamingNPCObject.map_npc_index),
        )
        super().__init__(inst, address, index, size)
        return inst

    @classmethod
    def from_index(cls, index: int) -> Self:
        return cls.from_reference(RoamingNPCObject.address, index, NPC_SIZE)

    def write(self):
        write_file.seek(self.pointer)
        write_file.write(self.npc_event_map_index.to_bytes(RoamingNPCObject.map_npc_event_index))
        write_file.write(self.sprite_index.to_bytes(RoamingNPCObject.sprite_index))
        write_file.write(self.map_index.to_bytes(RoamingNPCObject.map_index))
        write_file.write(self.map_npc_index.to_bytes(RoamingNPCObject.map_npc_index))
