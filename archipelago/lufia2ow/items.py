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
_UNUSED = set(range(454, 458)) | {data.AP_ITEM_INDEX}


def _unique_names() -> dict[int, str]:
    """Game item index -> AP item name. A few equipment names repeat (cursed copies); those get their index."""
    counts: dict[str, int] = {}
    for _, name, _ in data.ITEMS:
        counts[name] = counts.get(name, 0) + 1
    return {
        index: name if counts[name] == 1 else f"{name} #{index}"
        for index, name, _ in data.ITEMS
        if index not in _UNUSED
    }


ITEM_NAMES = _unique_names()
ITEM_CLASSIFICATION = {index: CLASSIFICATIONS[kind] for index, _, kind in data.ITEMS if index in ITEM_NAMES}
item_name_to_id = {name: BASE_ID + index for index, name in ITEM_NAMES.items()}

KEYS = frozenset(index for index in data.SCENARIO_ITEMS if index in ITEM_NAMES and ITEM_NAMES[index].endswith(" key"))
TOOLS = frozenset(data.TOOLS)
DRAGON_EGG = 43

_NOT_RANDOM = {0, DRAGON_EGG, 71, 466} | set(range(394, 398)) | set(range(412, 423))
"""Left out of random filler: No equip, Dragon egg (kept as is), SuhrCustom11 and Last (dev leftovers), casino coins,
the Iris treasures and the Ancient Cave's Power jelly and Jewel sonar."""


def _random_pool(kind: str) -> tuple[int, ...]:
    """Items of one classification for random filler: the first of each repeated name (later ones are cursed copies)."""
    seen: set[str] = set()
    out: list[int] = []
    for index, name, item_kind in data.ITEMS:
        if item_kind != kind or index not in ITEM_NAMES or index in _NOT_RANDOM or name in seen:
            continue
        seen.add(name)
        out.append(index)
    return tuple(out)


RANDOM_USEFUL = _random_pool("useful")
RANDOM_FILLER = _random_pool("filler")


class L2OWItem(Item):
    game = GAME
