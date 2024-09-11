"""Extra structures for sprites and palettes, for future support of gathering sprites and palettes from the ROM."""

from helpers.files import read_file, write_file
from typing import Self
from abc_.pointers import TablePointer
from tables import OverPaletteObject, CapPaletteObject, OverSpriteObject, SpriteMetaObject, TownSpriteObject


CAP_PALETTE_SIZE = sum([
    CapPaletteObject.color0,
    CapPaletteObject.color1,
    CapPaletteObject.color2,
    CapPaletteObject.color3,
    CapPaletteObject.color4,
    CapPaletteObject.color5,
    CapPaletteObject.color6,
    CapPaletteObject.color7,
    CapPaletteObject.color8,
    CapPaletteObject.color9,
    CapPaletteObject.colorA,
    CapPaletteObject.colorB,
    CapPaletteObject.colorC,
    CapPaletteObject.colorD,
    CapPaletteObject.colorE,
    CapPaletteObject.colorF,
])


class CapsulePallette(TablePointer):
    def __init__(self, data: bytes) -> None:
        self.palette = data

    @classmethod
    def from_index(cls, index: int) -> Self:
        return cls.from_table(CapPaletteObject.address, index)

    @classmethod
    def from_table(cls, address: int, index: int) -> Self:
        pointer = address + index * CAP_PALETTE_SIZE
        read_file.seek(pointer)
        inst = cls(read_file.read(CAP_PALETTE_SIZE))
        super().__init__(inst, address, index)
        return inst

    def write(self):
        write_file.seek(self.pointer)
        write_file.write(self.palette)
