"""Overworld Archipelago key items in the free scenario-item slots KEY26..KEY29 (Iris-Dev#33).

The Ship and Submarine are real items; the two progressive ones are tokens that key_items.asm turns into the next
ship or arrow upgrade in the field. Each slot gets its name and the key-item icon through the
:class:`~structures.item.Item` structure; everything else about them already matches the Engine.
"""

from iris.structures.item import Item


SHIP = 454
SUBMARINE = 455
PROGRESSIVE_SHIP = 456
PROGRESSIVE_ARROW = 457
KEY_ITEM_NAMES = {
    SHIP: "Ship",
    SUBMARINE: "Submarine",
    PROGRESSIVE_SHIP: "Prog. ship",
    PROGRESSIVE_ARROW: "Prog. arrow",
}
"""Slot -> in-game name (at most 12 characters)."""

ENGINE = 449


def apply_key_items() -> None:
    """Name the four slots and give them the Engine's key-item icon."""
    icon = Item.from_index(ENGINE).icon
    for index, name in KEY_ITEM_NAMES.items():
        item = Item.from_index(index)
        item.name_pointer.name = name.ljust(12)
        item.icon = icon
        item.write()
