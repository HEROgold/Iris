"""SNES 4bpp graphics codec: tile (de)interleaving and BGR555 palette conversion.

Pure, dependency-free helpers operating on ``bytes`` / lists of palette indices. No ROM handle and no
image library here -- ``structures/sprites.py`` layers PNG I/O (Pillow) and ROM offsets on top.

A SNES 4bpp tile is 8x8 pixels stored in 32 bytes as four bitplanes: planes 0/1 are row-interleaved in
the first 16 bytes (byte 0 = plane0 row0, byte 1 = plane1 row0, byte 2 = plane0 row1, ...) and planes 2/3
in the next 16 bytes. A pixel is ``p0 | p1<<1 | p2<<2 | p3<<3`` (0-15), read MSB-first per row.

Palette colours are 15-bit BGR555 little-endian u16: ``b<<10 | g<<5 | r``, each channel 5 bits.
"""

from collections.abc import Sequence

TILE_BYTES = 32
TILE_SIZE = 8
COLORS_PER_PALETTE = 16

type Rgb = tuple[int, int, int]
type PixelGrid = list[list[int]]


def deinterleave_tile(tile: bytes) -> list[int]:
    """Decode a 32-byte 4bpp tile into 64 palette indices (0-15), row-major."""
    if len(tile) != TILE_BYTES:
        msg = f"A 4bpp tile is {TILE_BYTES} bytes, got {len(tile)}."
        raise ValueError(msg)
    pixels = [0] * (TILE_SIZE * TILE_SIZE)
    for row in range(TILE_SIZE):
        plane0, plane1 = tile[row * 2], tile[row * 2 + 1]
        plane2, plane3 = tile[16 + row * 2], tile[16 + row * 2 + 1]
        for col in range(TILE_SIZE):
            bit = 7 - col
            pixels[row * TILE_SIZE + col] = (
                ((plane0 >> bit) & 1)
                | (((plane1 >> bit) & 1) << 1)
                | (((plane2 >> bit) & 1) << 2)
                | (((plane3 >> bit) & 1) << 3)
            )
    return pixels


def interleave_tile(pixels: Sequence[int]) -> bytes:
    """Encode 64 palette indices (0-15), row-major, into a 32-byte 4bpp tile."""
    if len(pixels) != TILE_SIZE * TILE_SIZE:
        msg = f"A tile is {TILE_SIZE * TILE_SIZE} pixels, got {len(pixels)}."
        raise ValueError(msg)
    tile = bytearray(TILE_BYTES)
    for row in range(TILE_SIZE):
        planes = [0, 0, 0, 0]
        for col in range(TILE_SIZE):
            bit = 7 - col
            value = pixels[row * TILE_SIZE + col]
            for plane in range(4):
                planes[plane] |= ((value >> plane) & 1) << bit
        tile[row * 2], tile[row * 2 + 1] = planes[0], planes[1]
        tile[16 + row * 2], tile[16 + row * 2 + 1] = planes[2], planes[3]
    return bytes(tile)


def data_to_pixels(data: bytes, width_tiles: int) -> PixelGrid:
    """Decode raw 4bpp tile data into a 2D pixel grid, tiles wrapped ``width_tiles`` per row."""
    if width_tiles < 1:
        msg = "width_tiles must be >= 1."
        raise ValueError(msg)
    tiles = [deinterleave_tile(data[i : i + TILE_BYTES]) for i in range(0, len(data) - len(data) % TILE_BYTES, TILE_BYTES)]
    rows_tiles = (len(tiles) + width_tiles - 1) // width_tiles
    grid: PixelGrid = [[0] * (width_tiles * TILE_SIZE) for _ in range(rows_tiles * TILE_SIZE)]
    for index, tile in enumerate(tiles):
        tile_x, tile_y = index % width_tiles, index // width_tiles
        for row in range(TILE_SIZE):
            for col in range(TILE_SIZE):
                grid[tile_y * TILE_SIZE + row][tile_x * TILE_SIZE + col] = tile[row * TILE_SIZE + col]
    return grid


def pixels_to_data(grid: PixelGrid) -> bytes:
    """Encode a 2D pixel grid back into raw 4bpp tile data (tiles left-to-right, top-to-bottom)."""
    height, width = len(grid), len(grid[0])
    if height % TILE_SIZE or width % TILE_SIZE:
        msg = f"Image must be a multiple of {TILE_SIZE}px in both axes, got {width}x{height}."
        raise ValueError(msg)
    out = bytearray()
    for tile_y in range(height // TILE_SIZE):
        for tile_x in range(width // TILE_SIZE):
            pixels = [
                grid[tile_y * TILE_SIZE + row][tile_x * TILE_SIZE + col]
                for row in range(TILE_SIZE)
                for col in range(TILE_SIZE)
            ]
            out += interleave_tile(pixels)
    return bytes(out)


def snes_color_to_rgb(value: int) -> Rgb:
    """Convert a 15-bit BGR555 colour to an 8-bit RGB tuple."""
    red, green, blue = value & 0x1F, (value >> 5) & 0x1F, (value >> 10) & 0x1F
    return (red * 255 // 31, green * 255 // 31, blue * 255 // 31)


def rgb_to_snes_color(rgb: Rgb) -> int:
    """Convert an 8-bit RGB tuple to the nearest 15-bit BGR555 colour."""
    red, green, blue = rgb
    red5, green5, blue5 = round(red * 31 / 255), round(green * 31 / 255), round(blue * 31 / 255)
    return (blue5 << 10) | (green5 << 5) | red5


def read_palette(data: bytes) -> list[Rgb]:
    """Decode a run of little-endian BGR555 u16 colours into RGB tuples."""
    return [snes_color_to_rgb(int.from_bytes(data[i : i + 2], "little")) for i in range(0, len(data) - len(data) % 2, 2)]


def write_palette(colors: Sequence[Rgb]) -> bytes:
    """Encode RGB tuples back into little-endian BGR555 u16 colours."""
    return b"".join(rgb_to_snes_color(color).to_bytes(2, "little") for color in colors)
