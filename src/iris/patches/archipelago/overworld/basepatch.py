"""Everything the overworld Archipelago base patch adds on top of a normal Iris build (Iris-Dev#6)."""

from pathlib import Path

from iris.constants import AP_OPT_BLUE_CHEST_COUNT, AP_SRAM_BLUE_CHESTS, AP_SRAM_BLUE_CHESTS_SAVED, RX_CODE_REGION
from iris.helpers.addresses import address_to_lorom
from iris.patcher import apply_asm_patch
from iris.patches.archipelago.overworld.ap_item import apply_ap_item
from iris.patches.archipelago.overworld.blue_chests import apply_blue_chests, write_blue_chests
from iris.patches.archipelago.overworld.config_block import write_config_block
from iris.patches.archipelago.overworld.docks import nearest_docks
from iris.patches.archipelago.overworld.hint_npcs import HintNpc, make_hint_slots
from iris.patches.archipelago.overworld.key_items import apply_key_items
from iris.patches.archipelago.overworld.remote_items import apply_remote_items
from iris.patches.archipelago.overworld.scenario_items import apply_scenario_item_mode, write_scenario_item_mode
from iris.patches.HEROgold.start_capsule import SPECIES_COUNT, default_name


RX_ASM = Path(__file__).parent / "rx.asm"


def apply_overworld_basepatch(hint_npcs: list[HintNpc]) -> None:
    """The hint slots, the config block header, receiving items and key items (rx.asm), the key-item slots, chests and
    grants holding the AP item (remote_items.asm), the scenario-item removal mode (scenario_items.asm, vanilla removals
    by default), Ancient Cave blue chests as checks (blue_chests.asm, off by default) and the AP item.

    The last asar run (the AP item's sprite) fixes the checksum.
    """
    make_hint_slots(hint_npcs)
    write_config_block()
    defines = {
        "capsule_names": _capsule_names(),
        "nearest_docks": _db(nearest_docks()),
        "blue_chests": f"${AP_SRAM_BLUE_CHESTS:06X}",
        "blue_chests_saved": f"${AP_SRAM_BLUE_CHESTS_SAVED:06X}",
        "blue_chest_count": f"${address_to_lorom(AP_OPT_BLUE_CHEST_COUNT):06X}",
    }
    apply_asm_patch(RX_ASM, defines=defines, code_region=RX_CODE_REGION)
    apply_key_items()
    apply_remote_items()
    write_scenario_item_mode()
    apply_scenario_item_mode()
    write_blue_chests()
    apply_blue_chests()
    apply_ap_item()


def _capsule_names() -> str:
    """Every species' default name, 5 bytes each, as an asar ``db`` list (rx_specials.asm's !capsule_names)."""
    names = b"".join(default_name(species).encode("ascii").ljust(5, b"\x00") for species in range(SPECIES_COUNT))
    return _db(names)


def _db(data: bytes) -> str:
    """``data`` as an asar ``db`` list."""
    return ",".join(f"${byte:02X}" for byte in data)
