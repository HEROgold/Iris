"""Rewrite a ROM object in place, or move it to free space when it no longer fits.

Generic over what the object is and how it is referenced: the caller passes the object's current
address and footprint, the search window for free space, and a ``repoint`` callback that stores the new
address wherever the game looks it up (a u16 table entry for capsule records, a 3-byte pointer for
ZoneData, ...).
"""

from collections.abc import Callable, Iterable

from helpers.files import write_file
from helpers.free_space import find_free_space


def write_relocatable(  # noqa: PLR0913 - three keyword-only options describe where/how to move
    data: bytes,
    old: int,
    old_size: int,
    *,
    repoint: Callable[[int], None],
    search: tuple[int, int],
    avoid: Iterable[int] = (),
) -> int:
    """Write ``data`` for the object at ``old`` (``old_size`` bytes) and return where it now lives.

    - Fits (``len(data) <= old_size``): written at ``old``; the leftover bytes of the old footprint are
      zeroed. ``repoint`` is not called.
    - Doesn't fit: written into free space found in ``search`` (skipping ``avoid``), the whole old
      footprint is zeroed, and ``repoint(new_address)`` is called.

    Raises ``ValueError`` before writing anything if no free space is large enough. The written bytes are
    read back and compared.
    """
    target = old if len(data) <= old_size else find_free_space(write_file, *search, len(data), avoid)
    write_file.seek(old)
    write_file.write(bytes(old_size))
    write_file.seek(target)
    write_file.write(data)
    if target != old:
        repoint(target)
    write_file.flush()
    write_file.seek(target)
    if write_file.read(len(data)) != data:
        msg = f"Relocated data at {target:#x} did not persist."
        raise ValueError(msg)
    return target
