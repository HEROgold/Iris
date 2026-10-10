"""Shared helpers for reserving ROM-expansion space.

The base Lufia II cart is a full 3MB with only ~1.2KB of genuinely blank space anywhere in it (see
``docs/encounter_scaling.md``) -- nowhere near enough for a patch's own data, and
``constants.EMPTY_BYTES`` does not describe real free bytes (its first range overlaps live game
data; see that constant's docstring). The only bytes provably safe to write into are ones that
don't exist yet: LoROM can address up to 4MB, so expanding the ROM file to that ceiling yields a
clean, genuinely blank megabyte at ``0x300000-0x3FFFFF``. Every fixed reservation in that area
(``constants.RESERVED_REGIONS``) uses these two functions instead of hand-rolling them, so the
"is this actually free" check is a runtime fact each run, not a documentation claim.
"""

from helpers.files import write_file


def ensure_rom_expanded(size: int) -> None:
    """Grow the ROM to at least ``size`` bytes. Idempotent: a no-op once the file is already big enough."""
    write_file.flush()
    write_file.seek(0, 2)  # end of file
    missing = size - write_file.tell()
    if missing > 0:
        write_file.write(bytes(missing))
        write_file.flush()


def assert_region_blank(region: range, *, owner: str) -> None:
    """Fail loudly if ``region`` is not all ``0x00``/``0xFF``.

    A region living past the original ROM's end is not enough on its own: an earlier ``.asm`` patch
    assembled with asar's ``freecode`` (which hands out any run of blank bytes it likes) has never
    heard of Iris' own reservations, so a real read-back check is the only thing standing between
    two patches silently overwriting each other's data.
    """
    write_file.flush()
    write_file.seek(region.start)
    occupied = write_file.read(len(region))
    if occupied.strip(b"\x00").strip(b"\xff"):
        msg = (f"{owner}'s reserved region {region.start:#08x}-{region.stop - 1:#08x} is not empty; "
               "an earlier asar `freecode` patch most likely claimed it. Apply this patch earlier, "
               "or move the reservation.")
        raise ValueError(msg)


def assert_no_overlaps(regions: list[range]) -> None:
    """Fail loudly if any two reserved regions intersect (a copy-pasted or typo'd address, say)."""
    ordered = sorted(regions, key=lambda r: r.start)
    for a, b in zip(ordered, ordered[1:], strict=False):
        if a.stop > b.start:
            msg = (f"Reserved regions overlap: {a.start:#08x}-{a.stop - 1:#08x} "
                   f"and {b.start:#08x}-{b.stop - 1:#08x}.")
            raise ValueError(msg)
