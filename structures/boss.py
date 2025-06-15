# FIXME: Dead file

from typing import Self

from abc_.pointers import Pointer
from helpers.files import write_file


class Boss(Pointer):
    def __init__(
        self,
        name: str,
        sprite_index: int,
        formation_index: int,
        battle_bgm_index: int,
    ) -> None:
        self.name = name
        self.sprite_index = sprite_index
        self.boss_formation_index = formation_index
        self.battle_bgm = battle_bgm_index

    @classmethod
    def from_pointer(cls, pointer: int) -> Self:
        # TODO: find out what data belongs where
        inst = cls(
            name="",
            sprite_index=0x0,
            formation_index=0x0,
            battle_bgm_index=0x0,
        )
        inst.pointer = pointer
        return inst

    def write(self) -> None:
        # TODO: Verify if this is the correct way to write the data
        write_file.seek(self.pointer)
        write_file.write(self.name.encode())
        write_file.write(bytes(self.sprite_index))
        write_file.write(bytes(self.boss_formation_index))
        write_file.write(bytes(self.battle_bgm))


class BossLocation(Pointer):
    def __init__(
        self,
        name: str,
        map_index: int,
        x: int,
        y: int,
        battle_bg_index: int,
        map_bgm: int,
    ) -> None:
        # TODO: add pointer to address location.
        self.name = name
        self.map_index = map_index
        self.npc_x = x
        self.npc_y = y
        self.battle_bg = battle_bg_index
        self.map_bgm = map_bgm

    def write(self) -> None:
        # TODO: Verify if this is the correct way to write the data
        write_file.seek(self.pointer)
        write_file.write(self.name.encode())
        write_file.write(bytes(self.map_index))
        write_file.write(bytes(self.npc_x))
        write_file.write(bytes(self.npc_y))
        write_file.write(bytes(self.battle_bg))
        write_file.write(bytes(self.map_bgm))
