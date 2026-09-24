"""Start a new game with a capsule monster, independent of the start map (``--start-capsule``).

Hooks the new-game setup's own capsule check at ``$83:AD80`` and gives the chosen species with the
game's routines, skipping the naming screen the story join shows. See ``start_capsule.asm`` for the
byte-level steps and ``docs/reference/capsule-ram.md`` for the RAM and routines involved.
"""

from pathlib import Path

from logger import iris
from patcher import apply_asm_patch
from structures.capsule import CapsuleMonster


_ASM = Path(__file__).parent / "start_capsule.asm"
SPECIES_COUNT = 7
FORMS_PER_SPECIES = 5
NAME_LENGTH = 5
EVENT_FLAGS = 0x7E077E  # event flag n: byte EVENT_FLAGS + n // 8, bit n % 8 (the game's helper at $80:BE30)
# Flag each species' story join scene sets right before event opcode ``81 XX`` (Foomy: map 0E, Hard Hat:
# map 70, ...). Setting it keeps the scene from giving the same capsule a second time.
STORY_FLAGS = (0x08, 0x09, 0x0C, 0x0D, 0x0E, 0x0F, 0x10)


def default_name(species: int) -> str:
    """The first word of the species' first-form name, cut to 5 characters (e.g. "Foomy")."""
    name = CapsuleMonster.from_index(species * FORMS_PER_SPECIES).name.rstrip("\x00")
    return name.split(" ")[0][:NAME_LENGTH]


def start_capsule(species: int, name: str | None = None) -> None:
    """Give capsule ``species`` (0-6) when a new game starts, named ``name`` (default: species name)."""
    if not 0 <= species < SPECIES_COUNT:
        msg = f"capsule species must be 0-{SPECIES_COUNT - 1}, got {species}"
        raise ValueError(msg)
    name = default_name(species) if name is None else name
    if not 1 <= len(name) <= NAME_LENGTH or not name.isascii():
        msg = f"capsule name must be 1-{NAME_LENGTH} ASCII characters, got {name!r}"
        raise ValueError(msg)

    iris.info(f"Starting new games with capsule species {species} named {name!r}.")
    padded = name.encode("ascii").ljust(NAME_LENGTH, b"\x00")
    defines = {
        "species": str(species),
        "flag_address": str(EVENT_FLAGS + STORY_FLAGS[species] // 8),
        "flag_mask": str(1 << (STORY_FLAGS[species] % 8)),
        **{f"n{i}": str(byte) for i, byte in enumerate(padded)},
    }
    apply_asm_patch(_ASM, defines=defines)
