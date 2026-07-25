"""Extra structures for sprites and palettes, for future support of gathering sprites and palettes from the ROM.

Raw sprite graphics data lives in two ROM regions (headerless offsets): 0xDFFF0-0xF2FFF (0x13010 bytes) and
0x2FE000 to end of ROM; see the SpriteBank / SpriteBankTail markers in src/lufia2.hexpat.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Self

from abc_.pointers import Pointer, ReferencePointer
from helpers.bits import read_little_int
from helpers.files import read_file, write_file
from helpers.snes_gfx import (
    COLORS_PER_PALETTE,
    TILE_BYTES,
    Rgb,
    data_to_pixels,
    pixels_to_data,
    read_palette,
)
from logger import iris
from tables import CapPaletteObject, CapSpritePTRObject, OverPaletteObject, OverSpriteObject, SpriteMetaObject

if TYPE_CHECKING:
    from helpers.snes_gfx import PixelGrid

PALETTE_BYTES = COLORS_PER_PALETTE * 2  # 16 BGR555 colours = 32 bytes


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


@dataclass(frozen=True)
class SpriteRegion:
    """A named, uncompressed 4bpp sprite region: raw tile data plus a 16-colour BGR555 palette.

    All offsets are headerless PC file offsets. ``palette_offset`` points at a 32-byte (16-colour) slot;
    the map-sprite half-palette at 0x133F00 holds several such slots at +0x00, +0x20, +0x40, ... The
    palette only affects displayed colours (and byte round-trip is preserved regardless, since import
    remaps by palette index) -- override it per sprite if the colours look wrong.
    """

    offset: int
    tile_count: int
    palette_offset: int = 0x133F00  # map-sprite half-palette, slot 0
    width_tiles: int = 16
    description: str = ""


# Confidently-viewable uncompressed regions (geometry from info/Reli + RealCitizen/L2_SMC_FileStruct.txt,
# headered doc offsets minus 0x200). Palettes default to the map-sprite half-palette; battle-sprite
# palettes live elsewhere and may need a --sprite-palette override. Add entries freely.
KNOWN_SPRITES: dict[str, SpriteRegion] = {
    "selan_battle": SpriteRegion(0x0CDE6C, 0xE0, description="Selan battle sprites"),
    "dekar_battle": SpriteRegion(0x0E3400, 0xD0, description="Dekar battle sprites"),
    "lexis_battle": SpriteRegion(0x0E4E00, 0xD0, description="Lexis battle sprites"),
    "maxim_battle": SpriteRegion(0x0EE000, 0xC0, description="Maxim battle sprites"),
    "guy_battle": SpriteRegion(0x0F9500, 0xA0, description="Guy battle sprites"),
    "item_sprites": SpriteRegion(0x0FA900, 0x8C, description="Item pickup sprites"),
    "enemy_map_sprites": SpriteRegion(0x0F737B, 0x86, width_tiles=4, description="Enemy overworld/map sprites (4x4)"),
    "bunny_girls": SpriteRegion(0x123C00, 0x40, description="Bunny-girl map sprites (RealCritical restore)"),
}


class SpriteSheet:
    """Extract/re-import an uncompressed 4bpp sprite region as an indexed PNG (paint.net-friendly).

    Extraction reads ``tile_count`` tiles at ``offset`` and the 16-colour palette at ``palette_offset``,
    then writes an indexed PNG. Import maps each pixel back to a palette index and writes the re-encoded
    4bpp bytes to ``write_file`` at ``offset`` -- an unedited extract->import is byte-identical.
    """

    def __init__(self, offset: int, tile_count: int, palette_offset: int, width_tiles: int = 16) -> None:
        self.offset = offset
        self.tile_count = tile_count
        self.palette_offset = palette_offset
        self.width_tiles = width_tiles

    @classmethod
    def from_region(cls, region: SpriteRegion) -> Self:
        return cls(region.offset, region.tile_count, region.palette_offset, region.width_tiles)

    @classmethod
    def named(cls, name: str) -> Self:
        if name not in KNOWN_SPRITES:
            known = ", ".join(sorted(KNOWN_SPRITES))
            msg = f"Unknown sprite {name!r}. Known sprites: {known}."
            raise ValueError(msg)
        return cls.from_region(KNOWN_SPRITES[name])

    def _read_palette(self) -> list[Rgb]:
        read_file.seek(self.palette_offset)
        return read_palette(read_file.read(PALETTE_BYTES))

    def _read_tile_data(self) -> bytes:
        read_file.seek(self.offset)
        return read_file.read(self.tile_count * TILE_BYTES)

    def export_png(self, path: Path) -> None:
        from PIL import Image  # noqa: PLC0415  (optional dependency, imported at call site)

        palette = self._read_palette()
        grid = data_to_pixels(self._read_tile_data(), self.width_tiles)
        image = Image.new("P", (len(grid[0]), len(grid)))
        image.putdata([index for row in grid for index in row])
        image.putpalette([channel for color in palette for channel in color])
        image.save(path)
        iris.info(f"Extracted {self.tile_count} tiles at {self.offset:#x} -> {path}")

    def import_png(self, path: Path) -> None:
        from PIL import Image  # noqa: PLC0415  (optional dependency, imported at call site)

        palette = self._read_palette()
        index_of = {color: i for i, color in enumerate(palette)}
        with Image.open(path) as opened:
            image = opened.convert("RGB")
        grid: PixelGrid = []
        inexact = 0
        for y in range(image.height):
            row: list[int] = []
            for x in range(image.width):
                color: Rgb = image.getpixel((x, y))  # type: ignore[assignment]
                index = index_of.get(color)
                if index is None:
                    index = min(range(len(palette)), key=lambda i: _color_distance(palette[i], color))
                    inexact += 1
                row.append(index)
            grid.append(row)
        data = pixels_to_data(grid)
        expected = self.tile_count * TILE_BYTES
        if len(data) != expected:
            msg = f"Image encodes {len(data)} bytes but region {self.offset:#x} holds {expected}; check dimensions."
            raise ValueError(msg)
        if inexact:
            iris.info(f"{inexact} pixel(s) not in palette; snapped to nearest colour.")
        write_file.seek(self.offset)
        write_file.write(data)
        iris.info(f"Imported {path} -> {self.tile_count} tiles at {self.offset:#x}")


def _color_distance(a: Rgb, b: Rgb) -> int:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2
