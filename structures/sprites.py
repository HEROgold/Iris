"""Extra structures for sprites and palettes, for future support of gathering sprites and palettes from the ROM."""

from typing import Self

from abc_.pointers import Pointer, ReferencePointer
from helpers.bits import read_little_int
from helpers.files import read_file, write_file
from tables import CapPaletteObject, CapSpritePTRObject, OverPaletteObject, OverSpriteObject, SpriteMetaObject


class CapsulePallette(ReferencePointer):
    def __init__(self, data: bytes) -> None:
        self.palette = data

    @classmethod
    def from_index(cls, index: int) -> Self:
        return cls.from_reference(CapPaletteObject.address, index, CapPaletteObject.size)

    @classmethod
    def from_reference(cls, address: int, index: int, size: int) -> Self:
        pointer = address + index * size
        read_file.seek(pointer)
        inst = cls(read_file.read(size))
        super().__init__(inst, address, index, size)
        return inst

    def write(self) -> None:
        write_file.seek(self.pointer)
        write_file.write(self.palette)

class CapsuleSprite(ReferencePointer):
    """
    Kureji only class.
    This class is used to represent the sprite data for the capsule monsters.
    """
    def __init__(self, sprite_pointer: int) -> None:
        self.sprite_pointer = sprite_pointer

    @classmethod
    def from_index(cls, index: int) -> Self:
        return cls.from_reference(CapSpritePTRObject.address, index, CapSpritePTRObject.sprite_pointer)

    @classmethod
    def from_reference(cls, address: int, index: int, size: int) -> Self:
        pointer = address + index * size
        read_file.seek(pointer)
        inst = cls(read_little_int(read_file, size))
        super().__init__(inst, address, index, size)
        return inst

    def write(self) -> None:
        write_file.seek(self.pointer)
        write_file.write(self.sprite_pointer.to_bytes(3, "little"))

class OverPallette(ReferencePointer):
    def __init__(self, pallette_index: int, pallette: bytes) -> None:
        self.pallette_index = pallette_index
        self.palette = pallette

    @classmethod
    def from_index(cls, index: int) -> Self:
        return cls.from_reference(OverPaletteObject.address, index, OverPaletteObject.size)

    @classmethod
    def from_reference(cls, address: int, index: int, size: int) -> Self:
        pointer = address + index * size
        read_file.seek(pointer)
        idx = read_little_int(read_file, 1)
        pallette = read_file.read(OverPaletteObject.unknown)
        inst = cls(idx, pallette)
        super().__init__(inst, address, index, size)
        return inst

    def write(self) -> None:
        write_file.seek(self.pointer)
        write_file.write(self.pallette_index.to_bytes())
        write_file.write(self.palette)

class OverSprite(ReferencePointer):
    def __init__(self, unknown: bytes, sprite_pointer: int) -> None:
        self.unknown = unknown
        self.sprite_index = sprite_pointer

    @classmethod
    def from_index(cls, index: int) -> Self:
        return cls.from_reference(OverSpriteObject.address, index, OverSpriteObject.size)

    @classmethod
    def from_reference(cls, address: int, index: int, size: int) -> Self:
        pointer = address + index * size
        read_file.seek(pointer)
        unknown = read_file.read(3)
        sprite_pointer = read_little_int(read_file, 3)
        inst = cls(unknown, sprite_pointer)
        super().__init__(inst, address, index, size)
        return inst

    def write(self) -> None:
        write_file.seek(self.pointer)
        write_file.write(self.unknown)
        write_file.write(self.sprite_index.to_bytes(3, "little"))

class SpriteMeta(ReferencePointer):
    address: int
    index: int
    pointer: int

    def __init__(self, width: bytes, height: bytes) -> None:
        self.width = width
        self.height = height

    def _validate(self) -> None:
        assert self.address
        assert self.index >= 0
        assert self.pointer

    @classmethod
    def from_index(cls, index: int) -> Self:
        return cls.from_reference(SpriteMetaObject.address, index, SpriteMetaObject.size)

    @classmethod
    def from_reference(cls, address: int, index: int, size: int) -> Self:
        pointer = address + index * size
        read_file.seek(pointer)
        width = read_file.read(1)
        height = read_file.read(1)
        inst = cls(width, height)
        super().__init__(inst, address, index, size)
        inst._validate()
        return inst

    def write(self) -> None:
        write_file.seek(self.pointer)
        write_file.write(self.width)
        write_file.write(self.height)

class TownSprite(Pointer):
    def __init__(self, unknown: int, sprite_index: int, sprite_pointer: int) -> None:
        self.unknown = unknown
        self.sprite_index = sprite_index
        self.sprite_pointer = sprite_pointer

    @classmethod
    def from_pointer(cls, pointer: int) -> Self:
        read_file.seek(pointer)
        inst = cls(
            read_little_int(read_file, 1),
            read_little_int(read_file, 1),
            read_little_int(read_file, 3),
        )
        inst.pointer = pointer
        return inst

    def write(self) -> None:
        write_file.seek(self.pointer)
        write_file.write(self.unknown.to_bytes(1, "little"))
        write_file.write(self.sprite_index.to_bytes(1, "little"))
        write_file.write(self.sprite_pointer.to_bytes(3, "little"))
