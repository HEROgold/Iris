"""The scenario-item removal mode, chosen per seed by the config block (Iris-Dev#26, docs/ap/scenario_items.md).

``scenario_items.asm`` hooks the story's "Remove item" worker: with ``AP_OPT_SCENARIO_ITEM_MODE`` at 0 the story takes
key items away as in vanilla, at 1 a held scenario item stays held. Every overworld Archipelago base patch, linear and
open world.
"""

from enum import IntEnum
from pathlib import Path

from iris.constants import AP_OPT_SCENARIO_ITEM_MODE, EXPANDED_ROM_SIZE, SCENARIO_ITEMS_CODE_REGION
from iris.helpers.addresses import address_to_lorom
from iris.helpers.files import write_file
from iris.helpers.rom_expansion import ensure_rom_expanded
from iris.patcher import apply_asm_patch


SCENARIO_ITEMS_ASM = Path(__file__).parent / "scenario_items.asm"


class ScenarioItemMode(IntEnum):
    """The values of ``AP_OPT_SCENARIO_ITEM_MODE``."""

    VANILLA_REMOVALS = 0
    """The story takes key items away as in vanilla."""
    NO_REMOVALS = 1
    """Key items stay held."""


def apply_scenario_item_mode() -> None:
    """Hook the remove worker so it reads the mode byte."""
    apply_asm_patch(
        SCENARIO_ITEMS_ASM,
        defines={"mode_byte": f"${address_to_lorom(AP_OPT_SCENARIO_ITEM_MODE):06X}"},
        code_region=SCENARIO_ITEMS_CODE_REGION,
    )


def write_scenario_item_mode(mode: ScenarioItemMode = ScenarioItemMode.VANILLA_REMOVALS) -> None:
    """Write the config block's mode byte (the base patch's default is vanilla removals)."""
    ensure_rom_expanded(EXPANDED_ROM_SIZE)
    write_file.seek(AP_OPT_SCENARIO_ITEM_MODE)
    write_file.write(bytes([mode]))
