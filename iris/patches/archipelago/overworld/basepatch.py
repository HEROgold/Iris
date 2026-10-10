"""Everything the overworld Archipelago base patch adds on top of a normal Iris build (Iris-Dev#6)."""

from iris.patches.archipelago.overworld.ap_item import apply_ap_item
from iris.patches.archipelago.overworld.config_block import write_config_block


def apply_overworld_basepatch() -> None:
    """The config block header and the AP item. asar runs last (in apply_ap_item), so its checksum covers both."""
    write_config_block()
    apply_ap_item()
