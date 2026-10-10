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


class L2OWItem(Item):
    game = GAME
