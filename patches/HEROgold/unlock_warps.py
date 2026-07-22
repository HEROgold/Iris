"""Unlock every Warp-spell destination from the start of the game.

Bakes the effect of the ``UNLOCK_WARP`` Game Genie codes (which only live in RAM) into the ROM by
hooking the new-game handoff and writing the destination flags. See ``unlock_warps.asm`` for the
byte-level details. terrorwave does not do this -- its open world uses the airship instead -- so this
is Iris-specific.
"""

from pathlib import Path

from logger import iris
from patcher import apply_asm_patch


_ASM = Path(__file__).parent / "unlock_warps.asm"


def unlock_all_warp_destinations() -> None:
    """Make every Warp-spell destination available on a fresh save."""
    iris.info("Unlocking all Warp destinations (baking UNLOCK_WARP into the new-game handoff).")
    apply_asm_patch(_ASM)
