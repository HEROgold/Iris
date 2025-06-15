from typing import Self

from abc_.pointers import Pointer, TablePointer
from constants import POINTER_SIZE
from helpers.bits import read_little_int, read_nth_bit
from helpers.files import read_file, write_file
from logger import iris
from tables import (
    ChestObject,
)

from .item import Item


# TODO: replace inheritance with Protocol (interface)
class AddressChest(TablePointer):
    def __init__(self, item: Item) -> None:
        self.item = item

    @classmethod
    def from_table(cls, address: int, index: int) -> Self:
        pointer = address + index * POINTER_SIZE
        read_file.seek(pointer)
        item_index = read_little_int(read_file, POINTER_SIZE)

        inst = cls(Item.from_index(item_index))
        # Init the required attributes manually.
        # It's not from a pointer table, this class IS the table.
        inst.address = address
        inst.index = index
        inst.pointer = pointer
        return inst

    def write(self) -> None:
        write_file.seek(self.pointer)
        write_file.write(self.item.index.to_bytes(2, "little"))

class PointerChest(Pointer):
    misc1: bytes
    misc2: bytes

    def __init__(self, item: Item) -> None:
        self.item = item

    @classmethod
    def from_pointer(cls, pointer: int) -> Self:
        read_file.seek(pointer)

        misc1 = read_file.read(1) # ChestObject.misc1
        misc2 = read_file.read(ChestObject.misc2)
        item_low_byte = read_file.read(ChestObject.item_low_byte)

        _u00 = read_nth_bit(misc1, 0)
        _u01 = read_nth_bit(misc1, 1)
        _u02 = read_nth_bit(misc1, 2)
        _u03 = read_nth_bit(misc1, 3)
        _u04 = read_nth_bit(misc1, 4)
        _u05 = read_nth_bit(misc1, 5)
        item_high_bit = read_nth_bit(misc1, 6)
        _u07 = read_nth_bit(misc1, 7)

        if item_high_bit == 0:
            item_index = int.from_bytes(item_low_byte)
        else:
            # Do some bit math to add the high bit
            item_index = int.from_bytes(item_low_byte, "little")
            iris.debug(f"High bit for item set. {pointer=}")

        # item_index = int.from_bytes(item_pointer, "little")
        inst = cls(Item.from_index(item_index))
        inst.misc1 = misc1
        inst.misc2 = misc2

        super().__init__(inst, pointer)
        return inst

    def write(self) -> None:
        write_file.seek(self.pointer)
        write_file.write(self.misc1)
        write_file.write(self.misc2)
        write_file.write(bytes(self.item))

        # if read_nth_bit(self.misc1, 6) == 0:
        #     write_file.write(self.item.index.to_bytes())
        # else:
        #     # Do some bit math to add the high bit
        #     write_file.write(set_nth_bit(b"\x00", 6) + self.item.index.to_bytes())
