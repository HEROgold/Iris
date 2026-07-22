"""Archipelago Lufia II "Ancient Cave" basepatch, split into native Iris data writes + asar code.

The bulk of the basepatch is injected 65816 code (RX/TX, goal tracking, architect mode, death link, shop
handling, and many fixes). That is assembled by the bundled asar from ``basepatch_code.asm`` via
:func:`patcher.apply_asm_patch`. The *static item data* that Iris already models -- the AP item, the six
party-member items, and the seven capsule-monster items (names + properties) -- is written here through the
:class:`~structures.item.Item` structure (name + properties) instead of asar ``DB`` directives, so it is
editable/randomizable the Iris way.

Descriptions, the "remove from scenario" list, and the AP-logo sprite stay in ``basepatch_code.asm``:
descriptions are not yet modeled by Iris (:pyattr:`Item.description` is a stub) and the sprite is a raw
binary blob, so asar remains the cleaner home for them.

Item index map (see the ``org`` addresses in ``basepatch.asm``):
    AP item                 -> index 458  (item id $01CA, overwrites "Key30")
    party members $01B2-$01B7 -> indices 434-439
    capsule monsters $01B8-$01BE -> indices 440-446
"""

from pathlib import Path

from enums.flags import (
    EquipableCharacter,
    EquipTypes,
    ItemEffects,
    ItemTypes,
    MenuIcon,
    Targeting,
    Usability,
)
from logger import iris
from patcher import apply_asm_patch
from structures.item import Item


_HERE = Path(__file__).parent
_ARCHIPELAGO_DIR = _HERE.parent  # include path so asar can resolve `incbin "ap_logo/ap_logo.bin"`

AP_ITEM_INDEX = 458
PARTY_INDICES = range(434, 440)   # Selan, Guy, Arty, Dekar, Tia, Lexis
CAPSULE_INDICES = range(440, 447)  # JELZE, FLASH, GUSTO, ZEPPY, DARBI, SULLY, BLAZE

# (name, 13-byte property row) exactly as the original basepatch.asm emitted them.
AP_ITEM: tuple[str, bytes] = ("AP item", bytes([0x00, 0x00, 0x00, 0xE4, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]))

PARTY_ITEMS: list[tuple[str, bytes]] = [
    ("Selan", bytes([0x40, 0x00, 0x00, 0xE9, 0x64, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])),
    ("Guy",   bytes([0x40, 0x00, 0x00, 0xE0, 0x64, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])),
    ("Arty",  bytes([0x40, 0x00, 0x00, 0xEB, 0x64, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])),
    ("Dekar", bytes([0x40, 0x00, 0x00, 0xED, 0x64, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])),
    ("Tia",   bytes([0x40, 0x00, 0x00, 0xE8, 0x64, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])),
    ("Lexis", bytes([0x40, 0x00, 0x00, 0xEF, 0x64, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])),
]

_CAPSULE_PROPS = bytes([0x00, 0x00, 0x00, 0xEE, 0x12, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
CAPSULE_ITEMS: list[tuple[str, bytes]] = [
    (name, _CAPSULE_PROPS) for name in ("JELZE", "FLASH", "GUSTO", "ZEPPY", "DARBI", "SULLY", "BLAZE")
]

_NAME_WIDTH = 12
_PROPERTY_ROW = 13  # ITEM_SIZE


def _write_item(index: int, name: str, row: bytes) -> None:
    """Overwrite one item's name and 13-byte property row in a single ``Item.write()``.

    Name and properties must be set on the *same* :class:`Item`: ``Item.write`` writes the name pointer
    first, so a separate name write would be clobbered by a later property write of the same item. The row
    is decoded field-by-field exactly as :meth:`Item.from_table` reads it.
    """
    if len(row) != _PROPERTY_ROW:
        msg = f"Property row for index {index} must be {_PROPERTY_ROW} bytes, got {len(row)}."
        raise ValueError(msg)
    if len(name) > _NAME_WIDTH:
        msg = f"Item name {name!r} exceeds {_NAME_WIDTH} chars."
        raise ValueError(msg)
    item = Item.from_index(index)
    item.name_pointer.name = name.ljust(_NAME_WIDTH)
    item.usability = Usability.from_byte(row[0:1])
    item.item_types = ItemTypes.from_byte(row[1:2])
    item.targeting = Targeting.from_byte(row[2:3])
    item.icon = MenuIcon.from_byte(row[3:4])
    item.sprite_index = row[4]
    item.price = int.from_bytes(row[5:7], "little")
    item.equip_types = EquipTypes.from_byte(row[7:8])
    item.equipability = EquipableCharacter.from_byte(row[8:9])
    item.item_effects = ItemEffects.from_bytes(row[9:11])  # Item.write re-reverses to restore these bytes
    item.unknown2 = row[11:13]
    item.write()


def _write_item_data() -> None:
    """Write the AP item, party-member items, and capsule-monster items via the Iris item structures."""
    ap_name, ap_props = AP_ITEM
    _write_item(AP_ITEM_INDEX, ap_name, ap_props)

    for index, (name, props) in zip(PARTY_INDICES, PARTY_ITEMS, strict=True):
        _write_item(index, name, props)

    for index, (name, props) in zip(CAPSULE_INDICES, CAPSULE_ITEMS, strict=True):
        _write_item(index, name, props)


def apply_ancient_cave_base() -> None:
    """Apply the full Ancient Cave basepatch: native item data (here) + injected code (asar)."""
    iris.info("Applying Archipelago Ancient Cave basepatch.")
    _write_item_data()
    # asar runs last so its checksum fix covers the item data written above.
    apply_asm_patch(_HERE/"basepatch_code.asm", [_ARCHIPELAGO_DIR], fix_checksum=True)
