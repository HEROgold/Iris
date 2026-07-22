"""Give Maxim the Warp spell from the very start of the game (dev/temp fix).

Warp lets the player teleport to any visited town from the field, which is handy while the
custom start-location work is still landing you in the wrong spot. Two ROM-level edits, both done
through Iris' own structures (no free-floating byte pokes):

1. **Caster mask** -- vanilla Warp (spell ``0x24``) is castable by Selan/Artea/Tia only; Maxim's bit
   is clear. We set it via :class:`Spell` so Maxim is actually allowed to cast it.
2. **Starting-spell list** -- each playable character's new-game template (the block
   :class:`PlayableCharacter` already reads its level/EXP/equipment from) ends with a ``0xFF``-terminated
   list of spell indices the character knows at game start. Maxim's is empty (just the terminator). We
   splice Warp's index in front of that terminator.

The template records are variable-length and packed back-to-back (Selan's is longer than Maxim's
precisely because she starts with more spells), so adding a spell to Maxim's list shifts every later
character down by one byte. :meth:`PlayableCharacter.set_starting_spells` handles that reflow; the one
byte the block grows by lands in the unused "Ancient Cave stat bonus" padding after Lexis, so nothing
the main game reads is disturbed.
"""

from enums.flags import CastableSpells
from logger import iris
from lookups.spells import Spells
from structures.character import PlayableCharacter


def maxim_starts_with_warp() -> None:
    """Make Maxim start every new game already knowing Warp, and able to cast it."""
    warp = Spells.WARP
    maxim = PlayableCharacter.from_index(0)

    if any(spell.index == warp.index for spell in maxim.starting_spells):
        iris.info("Maxim already starts with Warp; nothing to do.")
        return

    # 1) Let Maxim cast Warp -- his bit is clear in the vanilla caster mask (Selan/Artea/Tia only).
    warp.characters |= CastableSpells.MAXIM
    warp.write()

    # 2) Add Warp to Maxim's (empty) starting-spell list.
    maxim.starting_spells = *maxim.starting_spells, warp
    iris.info(f"Maxim now starts with Warp (spell {warp.index:#04x}); caster mask set and template updated.")
