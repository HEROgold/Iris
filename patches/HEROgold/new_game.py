"""The new-game hook: everything Iris sets up for a fresh save, in one asar patch at $03:ADC2.

asar can only hook the new-game handoff once, so every new-game feature is a switch on this one patch. Call
:func:`apply_new_game_hook` once per build. See ``new_game.asm`` for the byte-level details.

- ``unlock_warps``: every Warp-spell destination is available from the start (the ``UNLOCK_WARP`` Game Genie codes,
  which only live in RAM, baked into the ROM). terrorwave doesn't do this; its open world uses the airship.
- ``skip_tutorial``: the Secret Skills Cave (map 5) behaves as vanilla leaves it after the tutorial, and Maxim knows
  Reset. This sets event flags instead of editing event scripts, because grown event containers can't be placed yet
  (HER-232, HER-237). The flags come from the cave's own events and absynnonym's ``eventpatch_skip_tutorial.txt``.
"""

from pathlib import Path

from logger import iris
from patcher import apply_asm_patch


_ASM = Path(__file__).parent / "new_game.asm"

EVENT_FLAGS = 0x077E
"""Event flag n is bit n % 8 (low bit first) of $7E:077E + n // 8."""

TUTORIAL_FLAGS = (
    0x15,  # FINISHED_TUTORIAL: 05-C-04 opens the exit door (05) once per visit; Tia's Elcid scene (03-C-02) skips
    0x77,  # Tia's "I'll wait for you at the cave" scene (03-C-02) has run
    0xAC,  # the Reset lesson in LOAD_MAP 05-A-01 is done (that script skips when it's set)
    0x9E,  # 05-C-01 .. C-08: each trigger-tile lesson skips once its flag is set
    0x9F,
    0xA0,
    0xA1,
    0xA2,
    0xA3,
    0xAB,
)
"""Set at new game by ``skip_tutorial``. The Elcid "Bad news" scene (flag 0x96) still plays and starts the quest."""


def apply_new_game_hook(*, unlock_warps: bool = True, skip_tutorial: bool = False) -> None:
    """Install the new-game hook with the chosen features. Call once per build: a second call replaces the first."""
    iris.info(f"New-game hook: unlock_warps={unlock_warps}, skip_tutorial={skip_tutorial}.")
    apply_asm_patch(_ASM, defines={"unlock_warps": str(int(unlock_warps)), "skip_tutorial": str(int(skip_tutorial))})
