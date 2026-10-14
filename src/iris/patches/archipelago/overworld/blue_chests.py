"""Ancient Cave blue chests as count-based checks, chosen per seed by the config block (Iris-Dev#21).

``blue_chests.asm`` hooks the chest routine after the chest animation. With ``AP_OPT_BLUE_CHESTS_ENABLED`` on, the first
``AP_OPT_BLUE_CHEST_COUNT`` blue chests opened each bump the SRAM counter ``AP_SRAM_BLUE_CHESTS`` instead of giving
their item; after that, and with the option off, blue chests give their loot. rx.asm saves and loads the counter with the
save slot. Every overworld Archipelago base patch, linear and open world; the base patch writes 0/0 (off).
"""

from pathlib import Path

from iris.constants import (
    AP_OPT_BLUE_CHEST_COUNT,
    AP_OPT_BLUE_CHESTS_ENABLED,
    AP_SRAM_BLUE_CHESTS,
    BLUE_CHESTS_CODE_REGION,
    EXPANDED_ROM_SIZE,
)
from iris.helpers.addresses import address_to_lorom
from iris.helpers.files import write_file
from iris.helpers.rom_expansion import ensure_rom_expanded
from iris.patcher import apply_asm_patch


BLUE_CHESTS_ASM = Path(__file__).parent / "blue_chests.asm"
MAX_BLUE_CHESTS = 99
"""The apworld option's upper bound."""


def apply_blue_chests() -> None:
    """Hook the chest routine so blue chests read the config bytes."""
    apply_asm_patch(
        BLUE_CHESTS_ASM,
        defines={
            "enabled": f"${address_to_lorom(AP_OPT_BLUE_CHESTS_ENABLED):06X}",
            "count": f"${address_to_lorom(AP_OPT_BLUE_CHEST_COUNT):06X}",
            "counter": f"${AP_SRAM_BLUE_CHESTS:06X}",
        },
        code_region=BLUE_CHESTS_CODE_REGION,
    )


def write_blue_chests(count: int = 0) -> None:
    """Write the config block's blue-chest bytes: enabled = count > 0, then count as u16 (the base patch's default is
    off)."""
    if not 0 <= count <= MAX_BLUE_CHESTS:
        msg = f"blue chest count {count} is outside 0..{MAX_BLUE_CHESTS}"
        raise ValueError(msg)
    ensure_rom_expanded(EXPANDED_ROM_SIZE)
    write_file.seek(AP_OPT_BLUE_CHESTS_ENABLED)
    write_file.write(bytes([count > 0]) + count.to_bytes(2, "little"))
