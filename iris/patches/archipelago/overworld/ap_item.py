"""Overworld Archipelago "AP item" in a free item slot (KEY30, index 458).

Name and properties are written through the :class:`~structures.item.Item` structure; only the sprite stays
asm (a raw binary blob). Slots 454-458 (KEY26..KEY30) are unused in vanilla, so the main game is unaffected.
"""

from pathlib import Path

from iris.logger import iris
from iris.patcher import apply_asm_patch
from iris.patches.archipelago.ancient_cave.basepatch import AP_ITEM, _write_item


_HERE = Path(__file__).parent
_ARCHIPELAGO_DIR = _HERE.parent  # include path so asar can resolve `incbin "ap_logo/ap_logo.bin"`

AP_ITEM_INDEX = 458


def apply_ap_item() -> None:
    """Write the AP item's name and properties natively, then assemble its sprite."""
    iris.info("Applying Archipelago overworld AP item.")
    name, row = AP_ITEM
    _write_item(AP_ITEM_INDEX, name, row)
    # asar runs last so its checksum fix covers the item data written above.
    apply_asm_patch(_HERE/"ap_item.asm", [_ARCHIPELAGO_DIR], fix_checksum=True)
