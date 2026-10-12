"""Write the Archipelago config block's static header (Iris-Dev#8, docs/ap/config_block.md).

The base patch carries the magic and the layout version; everything else in the bank stays zero until the
apworld's per-seed tokens fill it (auth name, options, hints).
"""

from iris.constants import (
    AP_CONFIG_MAGIC,
    AP_CONFIG_MAGIC_OFFSET,
    AP_CONFIG_REGION,
    AP_CONFIG_VERSION,
    AP_CONFIG_VERSION_OFFSET,
    EXPANDED_ROM_SIZE,
)
from iris.helpers.files import write_file
from iris.helpers.rom_expansion import assert_region_blank, ensure_rom_expanded
from iris.logger import iris


def write_config_block() -> None:
    """Grow the ROM to 4MB if needed, then write the block's magic and version into its empty bank."""
    iris.info(f"Writing the Archipelago config block (layout version {AP_CONFIG_VERSION}).")
    ensure_rom_expanded(EXPANDED_ROM_SIZE)
    assert_region_blank(AP_CONFIG_REGION, owner="Archipelago config block")
    write_file.seek(AP_CONFIG_MAGIC_OFFSET)
    write_file.write(AP_CONFIG_MAGIC)
    write_file.seek(AP_CONFIG_VERSION_OFFSET)
    write_file.write(bytes([AP_CONFIG_VERSION]))
