"""Everything the overworld Archipelago base patch adds on top of a normal Iris build (Iris-Dev#6)."""

from pathlib import Path

from iris.patcher import apply_asm_patch
from iris.patches.archipelago.overworld.ap_item import apply_ap_item
from iris.patches.archipelago.overworld.config_block import write_config_block
from iris.patches.archipelago.overworld.hint_npcs import HintNpc, make_hint_slots
from iris.patches.archipelago.overworld.key_items import apply_key_items


RX_ASM = Path(__file__).parent / "rx.asm"


def apply_overworld_basepatch(hint_npcs: list[HintNpc]) -> None:
    """The hint slots, the config block header, receiving items and key items (rx.asm), the key-item slots and the AP item.

    The hint slots come first: asar's ``freecode`` must see the containers they move as taken. The last asar run (the
    AP item's sprite) fixes the checksum.
    """
    make_hint_slots(hint_npcs)
    write_config_block()
    apply_asm_patch(RX_ASM)
    apply_key_items()
    apply_ap_item()
