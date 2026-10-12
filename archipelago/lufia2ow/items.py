"""Items, from the vendored data export (data.py). An item's id is BASE_ID + its game item index, or BASE_ID + a
special id (characters, capsules, maidens; ``SPECIAL_ITEM_NAMES``)."""

from BaseClasses import Item, ItemClassification

from . import data


GAME = "Lufia II Overworld"
BASE_ID = 0x4C3200

CLASSIFICATIONS = {
    "progression": ItemClassification.progression,
    "useful": ItemClassification.useful,
    "filler": ItemClassification.filler,
}

SHIP, SUBMARINE, PROGRESSIVE_SHIP, PROGRESSIVE_ARROW = 454, 455, 456, 457
KEY_ITEM_NAMES = {
    SHIP: "Ship",
    SUBMARINE: "Submarine",
    PROGRESSIVE_SHIP: "Progressive Ship",
    PROGRESSIVE_ARROW: "Progressive Arrow",
}
"""The free scenario slots the base patch fills (data.KEY_ITEMS has their in-game names)."""
_UNUSED = {data.AP_ITEM_INDEX}


def _unique_names() -> dict[int, str]:
    """Game item index -> AP item name. A few equipment names repeat (cursed copies); those get their index."""
    counts: dict[str, int] = {}
    for _, name, _ in data.ITEMS:
        counts[name] = counts.get(name, 0) + 1
    names = {
        index: name if counts[name] == 1 else f"{name} #{index}"
        for index, name, _ in data.ITEMS
        if index not in _UNUSED
    }
    return names | KEY_ITEM_NAMES


CHARACTER_BASE, CAPSULE_BASE, MAIDEN_BASE = 0x200, 0x210, 0x220
"""Received-item ids the base patch handles itself (rx_specials.asm): character c is $0200 + c, capsule species s is
$0210 + s, maiden m is $0220 + m. They aren't game items: a chest or grant can't hold them (indexes stop at 0x1FF), so
they're always placed as the AP item and arrive through the receive list."""
CHARACTERS = ("Maxim", "Selan", "Guy", "Artea", "Tia", "Dekar", "Lexis")
"""Character index order (rx_specials.asm, iris.enums.flags FOUND_*)."""
CAPSULES = ("Foomy", "Shaggy", "Hard Hat", "Red Fish", "Myconido", "Raddisher", "Armor Dog")
"""Capsule species 0-6 by their first form's name in the US ROM (CapsuleMonster species * 5)."""
MAIDENS = ("Lisa", "Marie", "Clare")
"""Maiden 0-2 (rx_specials.asm: flags 0x1A-0x1C, read by the Doom Island barrier)."""
SPECIAL_ITEM_NAMES = (
    {CHARACTER_BASE + index: name for index, name in enumerate(CHARACTERS)}
    | {CAPSULE_BASE + index: f"Capsule {name}" for index, name in enumerate(CAPSULES)}
    | {MAIDEN_BASE + index: name for index, name in enumerate(MAIDENS)}
)
MAXIM = CHARACTER_BASE
"""Maxim always leads, so his item isn't in any pool (a leader option would change that)."""
OPEN_WORLD_SPECIALS = tuple(index for index in SPECIAL_ITEM_NAMES if index != MAXIM)
"""The special items an open-world pool holds: six characters, seven capsules, three maidens."""

ITEM_NAMES = _unique_names() | SPECIAL_ITEM_NAMES
ITEM_CLASSIFICATION = {index: CLASSIFICATIONS[kind] for index, _, kind in data.ITEMS if index in ITEM_NAMES}
ITEM_CLASSIFICATION |= dict.fromkeys(KEY_ITEM_NAMES, ItemClassification.progression)
ITEM_CLASSIFICATION |= {
    index: ItemClassification.useful if CAPSULE_BASE <= index < MAIDEN_BASE else ItemClassification.progression
    for index in SPECIAL_ITEM_NAMES
}
item_name_to_id = {name: BASE_ID + index for index, name in ITEM_NAMES.items()}

KEYS = frozenset(index for index in data.SCENARIO_ITEMS if index in ITEM_NAMES and ITEM_NAMES[index].endswith(" key"))
TOOLS = frozenset(data.TOOLS)
ARROW, FIRE_ARROW, ENGINE = 425, 426, 449
DRAGON_EGG = 43

_NOT_RANDOM = {0, DRAGON_EGG}
"""Left out of random filler: No equip and the Dragon eggs, which stay as they are."""


def _random_pool(kind: str) -> tuple[int, ...]:
    """Every item of one classification for random filler, cursed copies and leftovers included."""
    return tuple(
        index for index, _, item_kind in data.ITEMS
        if item_kind == kind and index in ITEM_NAMES and index not in KEY_ITEM_NAMES and index not in _NOT_RANDOM
    )


RANDOM_USEFUL = _random_pool("useful")
RANDOM_FILLER = _random_pool("filler")


class L2OWItem(Item):
    game = GAME
