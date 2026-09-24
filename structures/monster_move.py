from typing import Self

from abc_.pointers import ReferencePointer
from helpers.bits import read_little_int
from helpers.files import read_file, write_file
from tables import MonsterMoveObject


class MonsterMove(ReferencePointer):
    """One roaming-monster movement byte (``MonsterMoveObject`` @ ``0x27F6B5``).

    Known values: ``0x1F`` aggressive (chases the player), ``0x1B`` passive.
    """

    movement: int

    def __init__(self, movement: int) -> None:
        self.movement = movement

    def __repr__(self) -> str:
        return f"<MonsterMove: {self.index}, {self.movement:#04x}>"

    @classmethod
    def from_index(cls, index: int) -> Self:
        return cls.from_reference(MonsterMoveObject.address, index, MonsterMoveObject.size)

    @classmethod
    def from_reference(cls, address: int, index: int, size: int) -> Self:
        read_file.seek(address + index * size)
        inst = cls(read_little_int(read_file, MonsterMoveObject.movement))
        super().__init__(inst, address, index, size)
        return inst

    def write(self) -> None:
        write_file.seek(self.pointer)
        write_file.write(self.movement.to_bytes(MonsterMoveObject.movement, "little"))
