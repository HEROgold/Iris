"""A grant spot shows the item placed there (Iris-Dev#50): what Maxim holds up, and the object on the floor.

The base patch writes nothing for this. The export (``tools/export_ap_data.py``) finds each sprite operand in the base
ROM, and the Archipelago world writes the placed item's sprite over it as a same-size token
(``lufia2ow/grant_sprites.py``). Without a sprite for the item, the vanilla operand stays.

**Held sprite.** ``8C(XX-YY-ZZ)`` stores ``YY`` and ``ZZ`` in character ``XX``'s object ($80:A99D: ``$7FE5CE,X`` and
``$7FE5A6,X``); ``86(XX-40)`` then shows the character holding it up. Opening a chest fills the same two fields
($8E:A229-$8E:A25E): an item whose sprite byte (item record byte 4, :attr:`Item.sprite_index`) is below 0x40 gets
``YY = 0A, ZZ = sprite``, a tool (0x40-0x45) ``YY = 18, ZZ = sprite - 0x40``. That is the rule :func:`held_icon` copies,
and chests show it on every map, so it works at every grant. Sprite 0 (coins, "no chest sprite") counts as no icon,
except for the AP item: its sprite is 0, whose graphics at $9F:A900 the base patch replaces with the AP logo
(``ap_item.asm``), so :data:`AP_HELD_ICON` shows the logo. The one-off ``YY`` values of the story grants (``0C`` crown,
``16`` ruby apple, ``1A`` pretty flower, ``1B`` ruby icon) are only shown on their own map, so they aren't reused.

**Floor sprite.** The map's NPC-load script loads the floor object with ``68(slot-sprite)``. A map sprite id indexes
the 251-entry table at ``$CF:F000`` (headerless 0x27F000), each a 5-byte record: shape, palette, LoROM pointer to the
graphics. It is a whole sprite, not a frame or palette of the map's own set, so another map's id loads too: open world
puts boss sprites and the crown (0x48, ``bosses.BEATEN_SPRITE``) on other maps the same way. The four item sprites
of :data:`MAP_SPRITES` all use palette 1. The scripts only hide (``2E``), show (``2D``) and move (``30``/``A3``, a movement
command) the object, nothing tied to one sprite's frames. The Door key spot's ``68(50-9E)`` is the boss who holds the
key, not the key, so it isn't a floor object here; the Ruby apple map's other object ``68(53-7D)`` isn't the grant's.

There is no map sprite for the AP logo: the map sprite table is full (its records start right after its 251 pointers)
and the logo is a one-frame item-sheet tile in the item palette. A remote item keeps the vanilla floor sprite.

Open world drops these story grants; of its grants only the egg wishes ``9F-B-50`` and the Ancient Cave's ``F1-C-01``
have an ``8C``, and neither is a location. Its base patch doesn't change.
"""

from dataclasses import dataclass

from iris.patches.archipelago.overworld.ap_item import AP_ITEM_INDEX
from iris.structures.event_script.containers import MapEvent
from iris.structures.event_script.dump import _signature
from iris.structures.event_script.script import EventScript
from iris.structures.item import Item
from iris.tables import ItemObject


HOLD_ITEM = 0x8C
LOAD_NPC = 0x68
GRANT_OPS = (0x20, 0x21)
ITEM_SHEET = 0x0A
"""``YY`` of the generic item sprites, sprite bytes 0x01-0x3F."""
TOOL_SHEET = 0x18
"""``YY`` of the tool sprites, sprite bytes 0x40 and up (``ZZ`` = sprite - 0x40)."""
TOOL_BASE = 0x40
NO_ICON = 0x00
AP_HELD_ICON = (ITEM_SHEET, NO_ICON)
"""The AP item's held sprite: item sprite 0, which the base patch draws as the AP logo (``ap_item.asm``)."""


@dataclass(frozen=True)
class FloorObject:
    map_index: int
    signature: str
    """The grant script."""
    item: int
    """The grant's vanilla item."""
    slot: int
    """The NPC slot the map's NPC-load script loads with ``68(slot-sprite)``."""
    sprite: int
    """The vanilla map sprite."""


FLOOR_OBJECTS = (
    FloorObject(0x14, "14-C-03", 459, 0x54, 0x48),  # Crown
    FloorObject(0x26, "26-B-18", 452, 0x59, 0x61),  # Ruby icon (Glass angel)
    FloorObject(0x2A, "2A-B-18", 460, 0x52, 0x6C),  # Ruby apple
    FloorObject(0x7E, "7E-C-01", 451, 0x51, 0x66),  # Pretty flower
)
MAP_SPRITES = {floor.item: floor.sprite for floor in FLOOR_OBJECTS}
"""Item -> its map sprite: the four items a grant leaves on the floor."""


def held_icon(sprite: int) -> tuple[int, int] | None:
    """``8C``'s ``(YY, ZZ)`` for an item with sprite byte ``sprite``, as a chest shows it; ``None`` for no icon."""
    if sprite == NO_ICON:
        return None
    if sprite >= TOOL_BASE:
        return TOOL_SHEET, sprite - TOOL_BASE
    return ITEM_SHEET, sprite


def held_icons() -> dict[int, tuple[int, int]]:
    """Item -> held ``(YY, ZZ)`` for every item with an icon, read from the active session's item data."""
    Item.reread(0)
    icons = {index: held_icon(Item.from_index(index).sprite_index) for index in range(ItemObject.count)}
    return {index: icon for index, icon in icons.items() if icon is not None and index != AP_ITEM_INDEX}


def _script(map_index: int, signature: str) -> EventScript:
    map_event = MapEvent.from_index(map_index)
    map_event.read()
    return next(
        script
        for event_list in map_event.event_lists
        for script in event_list.events
        if _signature(map_index, script) == signature
    )


def held_operands(map_index: int, signature: str) -> list[tuple[int, int]]:
    """(offset of the grant's item byte, offset of its ``8C``'s ``YY``) per grant in the script that an ``8C`` precedes.

    An ``8C`` belongs to the first grant after it; a grant with no ``8C`` since the previous grant has none.
    """
    script = _script(map_index, signature)
    out = []
    held = None
    for instruction in script.instructions:
        if instruction.opcode == HOLD_ITEM:
            held = script.pointer + instruction.line + 2
        elif instruction.opcode in GRANT_OPS and held is not None:
            out.append((script.pointer + instruction.line + 1, held))
            held = None
    return out


def floor_operand(floor: FloorObject) -> int:
    """Offset of the floor object's sprite byte in its map's NPC-load script (``68(slot-sprite)``)."""
    map_event = MapEvent.from_index(floor.map_index)
    map_event.read()
    script = map_event.npc_script
    found = [
        script.pointer + instruction.line + 2
        for instruction in script.instructions
        if instruction.opcode == LOAD_NPC and list(instruction.operands) == [floor.slot, floor.sprite]
    ]
    if len(found) != 1:
        msg = f"Map {floor.map_index:#04x} loads slot {floor.slot:#x} with sprite {floor.sprite:#x} {len(found)} times."
        raise ValueError(msg)
    return found[0]
