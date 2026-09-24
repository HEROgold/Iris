"""Dev patch for quick testing (``--debug-party``): every character starts at level 99 with 999 base stats.

Writes only the party template's level byte and the base-stat block (``CharacterObject``). It doesn't call
``PlayableCharacter.write``, which also reflows the starting-spell lists.
"""

from helpers.files import write_file
from logger import iris
from structures.character import PlayableCharacter
from tables import CharacterObject


MAX_LEVEL = 99
MAX_STAT = 999
CHARACTER_COUNT = 7


def max_out_party() -> None:
    iris.info("Debug party: level 99 and 999 base stats for every character.")
    for index in range(CHARACTER_COUNT):
        character = PlayableCharacter.from_index(index)
        character.level.level = MAX_LEVEL
        character.level.write()
        write_file.seek(CharacterObject.address + index * CharacterObject.size)
        for width in (CharacterObject.hp, CharacterObject.mp, CharacterObject.str, CharacterObject.agl,
                      CharacterObject.int, CharacterObject.gut, CharacterObject.mgr):
            write_file.write(MAX_STAT.to_bytes(width, "little"))
        iris.info(f"  {character.name}: level {MAX_LEVEL}, stats {MAX_STAT}.")
