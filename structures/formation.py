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

from abc_.pointers import AddressPointer
from structures.monster import Monster
from tables import FormationObject


class BattleFormation(AddressPointer):
    max_monsters = 8

    def __init__(self, monsters: list[Monster]) -> None:
        self.monsters = monsters

    @classmethod
    def from_index(cls, index: int) -> Self:
        return cls.from_table(FormationObject.address, index)

    @classmethod
    def from_table(cls, address: int, index: int) -> Self:
        pointer = address + index * 8
        read_file.seek(pointer)

        _0 = read_file.read(1)
        _1 = read_file.read(1)
        _2 = read_file.read(1)
        _3 = read_file.read(1)
        _4 = read_file.read(1)
        _5 = read_file.read(1)
        _6 = read_file.read(1)
        _7 = read_file.read(1)

        monsters = [_0,_1,_2,_3,_4,_5,_6,_7,]
        while b"\xFF" in monsters:
            monsters.pop(monsters.index(b"\xFF"))

        monsters_test = [
            Monster.from_index(int.from_bytes(i))
            for i in monsters
        ]

        for idx, monster in zip(monsters, monsters_test):
            m_idx = int.from_bytes(idx)
            assert m_idx == monster.index

        inst = cls(monsters_test)
        inst.address = address
        inst.index = index
        inst.pointer = pointer
        return inst

    def write(self) -> None:
        write_file.seek(self.pointer)
        for monster in self.monsters:
            write_file.write(monster.index.to_bytes())


class BossFormation(AddressPointer):
    pass

class MapFormation(AddressPointer):
    pass


# TODO: BossFormationObject
# TODO: MapFormationsObject)
