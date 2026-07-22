from typing import TYPE_CHECKING, Self

from abc_.pointers import Pointer, TablePointer
from constants import POINTER_SIZE
from helpers.bits import read_little_int, read_nth_bit
from helpers.files import read_file, write_file
from logger import iris
from tables import (
    ChestObject,
)

from .item import Item


if TYPE_CHECKING:
    from structures.chest_location import ChestLocation


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
        iris.debug(f"Writing AddressChest item={self.item.index} → {self.pointer=:#08x}")
        write_file.seek(self.pointer)
        write_file.write(self.item.index.to_bytes(2, "little"))

class PointerChest(Pointer):
    misc1: bytes
    misc2: bytes # Seems to be some form of index.
    index: int | None = None  # global chest index, when built via from_index (identity for tracing back)

    def __init__(self, item: Item) -> None:
        self.item = item

    @classmethod
    def from_index(cls, chest_index: int) -> Self:
        """Build a chest by its global chest index (keeps the index so it can trace back to its location)."""
        inst = cls.from_pointer(ChestObject.pointers[chest_index])
        inst.index = chest_index
        return inst

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

        item_index = int.from_bytes(item_low_byte, "little")
        if item_high_bit:
            item_index |= 0x100  # 9-bit item index: high bit lives in misc1 bit 6
            iris.debug(f"High bit for item set. {pointer=}")

        inst = cls(Item.from_index(item_index))
        inst.misc1 = misc1
        inst.misc2 = misc2

        super().__init__(inst, pointer)
        return inst

    def write(self) -> None:
        iris.debug(f"Writing PointerChest item={self.item.index} → {self.pointer=:#08x}")
        # Encode the 9-bit item index: bit 6 of misc1 is the high bit, item_low_byte the low 8 bits.
        # (Ports terrorwave ChestObject.set_item; preserves the other misc1 flag bits.)
        misc1 = int.from_bytes(self.misc1, "little")
        if self.item.index & 0x100:
            misc1 |= 1 << 6
        else:
            misc1 &= ~(1 << 6)
        write_file.seek(self.pointer)
        write_file.write(bytes([misc1]))
        write_file.write(self.misc2)
        write_file.write(bytes([self.item.index & 0xFF]))

    @property
    def location(self) -> "ChestLocation | None":
        """This chest's ChestLocation (map + placement), or None if it has no known map.

        Only normal (red) chests are in the ported chest->map table; blue/ancient chests and chests
        built via ``from_pointer`` (no index) return None.
        """
        if self.index is None:
            return None
        from structures.chest_location import ChestLocation  # noqa: PLC0415  (avoid import cycle at load)

        try:
            return ChestLocation.from_index(self.index)
        except KeyError:
            return None
