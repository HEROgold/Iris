"""Items, from the vendored data export (data.py). An item's id is BASE_ID + its game item index."""

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


ITEM_NAMES = _unique_names()
ITEM_CLASSIFICATION = {index: CLASSIFICATIONS[kind] for index, _, kind in data.ITEMS if index in ITEM_NAMES}
ITEM_CLASSIFICATION |= dict.fromkeys(KEY_ITEM_NAMES, ItemClassification.progression)
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
