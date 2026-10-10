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
NO_STARTING_ARROW = (
    (0x1AE62, bytes([0x00]), bytes([0xFF])),
    (0x2B2CA, bytes([0xA9, 0x01]), bytes([0x00, 0x00])),
)
"""(headerless offset, vanilla bytes, bytes) that make Maxim start without the Arrow, for the apworld to write per seed.

0x1AE62 is the operand of ``LDA #$00 : STA $0926`` in the new-game initialiser ($83:AE61): tool slot 0 gets tool 0, the
Arrow; ``$FF`` leaves it empty. 0x2B2CA is the last word of Maxim's starting equipment in his character record ($85:B2CA,
item 425, the Arrow; terrorwave's ``starting_tool``); 0 is an empty slot, as in his other ones. Not checked in an
emulator yet."""


def apply_key_items() -> None:
    """Name the four slots and give them the Engine's key-item icon."""
    icon = Item.from_index(ENGINE).icon
    for index, name in KEY_ITEM_NAMES.items():
        item = Item.from_index(index)
        item.name_pointer.name = name.ljust(12)
        item.icon = icon
        item.write()
