"""Everything the overworld Archipelago base patch adds on top of a normal Iris build (Iris-Dev#6)."""

from pathlib import Path

from iris.patcher import apply_asm_patch
from iris.patches.archipelago.overworld.ap_item import apply_ap_item
from iris.patches.archipelago.overworld.config_block import write_config_block


RX_ASM = Path(__file__).parent / "rx.asm"


def apply_overworld_basepatch() -> None:
    """The config block header, receiving items (rx.asm) and the AP item. The last asar run fixes the checksum."""
    write_config_block()
    apply_asm_patch(RX_ASM)
    apply_ap_item()
