"""Chests and grants holding the AP item say who the item is for and give nothing locally (Iris-Dev#19).

``remote_items.asm`` hooks the chest routine and the grant opcodes. A chest shows its entry in the remote-text table
(``AP_REMOTE_CHEST_TEXT_*``, filled by the apworld's tokens) instead of "Found AP item"; a grant's message is its own
slot (``grant_text``). Neither hands the AP item over, and both still set the chest's opened bit or the grant's flag.
Every overworld Archipelago base patch: open world's chests and grants hold remote items too.
"""

from pathlib import Path

from iris.constants import (
    AP_REMOTE_CHEST_TEXT_COUNT,
    AP_REMOTE_CHEST_TEXT_ENTRY_SIZE,
    AP_REMOTE_CHEST_TEXT_OFFSET,
    REMOTE_ITEMS_CODE_REGION,
)
from iris.helpers.addresses import address_to_lorom
from iris.patcher import apply_asm_patch
from iris.patches.archipelago.overworld.ap_item import AP_ITEM_INDEX


REMOTE_ITEMS_ASM = Path(__file__).parent / "remote_items.asm"


def apply_remote_items() -> None:
    apply_asm_patch(
        REMOTE_ITEMS_ASM,
        defines={
            "ap_item": f"${AP_ITEM_INDEX:04X}",
            "table": f"${address_to_lorom(AP_REMOTE_CHEST_TEXT_OFFSET):06X}",
            "entry_size": str(AP_REMOTE_CHEST_TEXT_ENTRY_SIZE),
            "chest_count": str(AP_REMOTE_CHEST_TEXT_COUNT),
        },
        code_region=REMOTE_ITEMS_CODE_REGION,
    )
