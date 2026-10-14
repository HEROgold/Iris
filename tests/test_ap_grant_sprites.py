"""A grant spot shows the placed item in Maxim's hands and on the floor (Iris-Dev#50).

The base patch changes nothing; the world writes the item's held icon over each grant's ``8C`` and its map sprite over
the floor object's ``68``. These check the rule against the vanilla grants and chests, and that the operands the
export finds in the base ROM are the vanilla ones.
"""

from collections.abc import Iterator

import pytest
from iris.build import build
from iris.enums.patches import Patch
from iris.helpers import files
from iris.helpers.files import open_rom, output_bytes, read_file, session, use
from iris.patches.archipelago.overworld.ap_item import AP_ITEM_INDEX
from iris.patches.archipelago.overworld.grant_sprites import (
    AP_HELD_ICON,
    FLOOR_OBJECTS,
    HOLD_ITEM,
    ITEM_SHEET,
    MAP_SPRITES,
    floor_operand,
    held_icon,
    held_icons,
    held_operands,
)
from iris.structures.item import Item
from iris.tables import select, selected


pytest.importorskip("bsdiff4")

from tools.build_ap_basepatch import OPTIONS, vanilla_image
from tools.export_ap_data import _grant_sprites, _grants, _moved


AP_LOGO = 0x0FA900
"""$9F:A900: item sprite 0's graphics, the AP logo in the base patch (``ap_item.asm``)."""
ITEM_SPRITE_SIZE = 0x80
CHEST_SPRITE_CODE = 0x07423F
"""$8E:A23F: a chest's item sprite (``LDA $0B88 : CMP #$40``) goes to YY 0A, or YY 18 with ZZ - 0x40."""
CHEST_SPRITE_BYTES = bytes.fromhex("ad880bc940901138e9408fa6e57fa9188fcee57f")


@pytest.fixture
def restore() -> Iterator[None]:
    rom, patch = session(), selected()
    yield
    select(patch)
    use(rom)


def _vanilla() -> bytes:
    image = vanilla_image(files.original_file)
    select(Patch.VANILLA)
    open_rom(image)
    return image


@pytest.mark.usefixtures("restore")
def test_vanilla_generic_grants_hold_the_items_chest_icon() -> None:
    """Every vanilla ``8C(XX-0A-ZZ)`` grant but the Mermaid jade's (a ball) holds the icon its item shows from a chest."""
    _vanilla()
    read_file.seek(CHEST_SPRITE_CODE)
    assert read_file.read(len(CHEST_SPRITE_BYTES)) == CHEST_SPRITE_BYTES
    checked = 0
    for map_index, signature, offset, item, _, _ in _grants():
        held = dict(held_operands(map_index, signature)).get(offset)
        if held is None:
            continue
        read_file.seek(held)
        sheet, sprite = read_file.read(2)
        if sheet != ITEM_SHEET or signature in {"9F-B-50", "BF-B-2D"}:  # egg wishes: one 8C for several grants
            continue
        assert held_icon(Item.from_index(item).sprite_index) == (sheet, sprite), signature
        checked += 1
    assert checked >= 6


def test_held_icon_follows_the_chest_rule() -> None:
    assert held_icon(0x00) is None
    assert held_icon(0x01) == (0x0A, 0x01)
    assert held_icon(0x44) == (0x18, 0x04)


@pytest.mark.usefixtures("restore")
def test_base_rom_operands_are_the_vanilla_ones() -> None:
    image = _vanilla()
    vanilla_grants = _grants()
    build(image, OPTIONS)
    rom = output_bytes()
    grants = _moved(vanilla_grants, open_world=False)
    held, floor = _grant_sprites(grants)
    assert len(held) >= 12
    for operand in held.values():
        assert rom[operand - 2] == HOLD_ITEM
    assert sorted(rom[operand] for operand in floor.values()) == sorted(MAP_SPRITES.values())
    assert {floor_operand(spot) for spot in FLOOR_OBJECTS} == set(floor.values())
    assert rom[AP_LOGO : AP_LOGO + ITEM_SPRITE_SIZE] != image[AP_LOGO : AP_LOGO + ITEM_SPRITE_SIZE]
    assert Item.from_index(AP_ITEM_INDEX).sprite_index == AP_HELD_ICON[1]
    icons = held_icons()
    assert AP_ITEM_INDEX not in icons
    assert icons[108] == (0x0A, 0x01)  # Gades' blade: a sword
