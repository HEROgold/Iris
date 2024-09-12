# Code for reference when creation BattleFormation class
# class FormationObject:
#     monster_indexes: list = 8
#     address = 0xBBE93
#     count = 192
# class BossFormationObject:
#     reference_pointer = 2
#     address = 0xBC53D
#     count = 39

from helpers.files import read_file, write_file
from typing import Self

from abc_.pointers import Pointer
from structures.monster import Monster


class BattleFormation(Pointer):
    address: int | None
    index: int | None
    max_monsters = 8

    def __init__(self, monsters: list[Monster]) -> None:
        self.monsters = monsters

    # We Don't implement a from_index method, since there's 3 tables to read from.

    @classmethod
    def from_table(cls, address: int, index: int) -> Self:
        pointer = address + index * 8
        read_file.seek(pointer)
        inst = cls.from_pointer(pointer)
        inst.address = address
        inst.index = index
        return inst

    @classmethod
    def from_pointer(cls, pointer: int) -> Self:
        read_file.seek(pointer)
        _0 = read_file.read(1)
        _1 = read_file.read(1)
        _2 = read_file.read(1)
        _3 = read_file.read(1)
        _4 = read_file.read(1)
        _5 = read_file.read(1)
        _6 = read_file.read(1)
        _7 = read_file.read(1)

        monsters = [
            Monster.from_index(int.from_bytes(i))
            for i in [_0, _1, _2, _3, _4, _5, _6, _7]
        ]

        inst = cls(monsters)
        inst.pointer = pointer
        return inst

    def write(self) -> None:
        write_file.seek(self.pointer)
        for monster in self.monsters:
            write_file.write(monster.index.to_bytes())
