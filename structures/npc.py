from helpers.files import read_file
from typing import Self
from abc_.pointers import TablePointer
from helpers.bits import read_little_int
from tables import RoamingNPCObject

class RoamingNPC(TablePointer):
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
    def from_table(cls, address: int, index: int) -> Self:
        inst = cls(
            npc_event_map_index=read_little_int(read_file, RoamingNPCObject.map_npc_event_index),
            sprite_index=read_little_int(read_file, RoamingNPCObject.sprite_index),
            map_index=read_little_int(read_file, RoamingNPCObject.map_index),
            map_npc_index=read_little_int(read_file, RoamingNPCObject.map_npc_index),
        )
        super().__init__(inst, address, index)
        return inst
