"""Helpers to convert between headered and unheadered ROMs.

.smc and .sfc files are both headered ROMs,
but .smc files have a 512-byte header at the beginning of the file.
This header is not part of the actual ROM data, and it can cause issues when patching or modifying the ROM.
This module provides functions to convert between headered and unheadered ROMs, allowing for easier"""

OFFSET = 0x200  # The offset of the header in a .smc file

def remove_header_offset(address: int) -> int:
    """Convert an offset in a headered ROM to the corresponding offset in an unheadered ROM."""
    return address - OFFSET if address >= OFFSET else address
