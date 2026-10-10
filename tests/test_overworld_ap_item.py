"""The overworld AP item lives in a free item slot (KEY30) and is never granted by vanilla content."""

from enums.flags import MenuIcon
from helpers.files import write_file
from patches.archipelago.overworld.ap_item import AP_ITEM_INDEX, apply_ap_item
from structures.chest import AddressChest, PointerChest
from structures.event_script.containers import MapEvent
from structures.item import Item
from tables import AncientChest1Object, AncientChest2Object, BlueChestObject, ChestObject, MapEventObject
from tests.reset_file import reset_file


CANDIDATE_INDICES = range(454, 459)  # KEY26..KEY30


def test_ap_item_written() -> None:
    try:
        apply_ap_item()
        write_file.flush()
        item = Item.from_index(AP_ITEM_INDEX)
        assert item.name_pointer.name.strip() == "AP item"
        assert item.icon == MenuIcon.from_byte(bytes([0xE4]))
        assert item.sprite_index == 0
    finally:
        reset_file()


def test_candidate_slots_unused_in_vanilla() -> None:
    held: set[int] = set()
    held.update(PointerChest.from_index(i).item.index for i in range(len(ChestObject.pointers)))
    for table in (BlueChestObject, AncientChest1Object, AncientChest2Object):
        held.update(AddressChest.from_table(table.address, i).item.index for i in range(table.count))
    assert not held & set(CANDIDATE_INDICES), "a chest holds a candidate slot"

    granted: set[int] = set()
    for map_index in range(MapEventObject.count):
        map_event = MapEvent.from_index(map_index)
        map_event.read()
        for event_list in map_event.event_lists:
            for script in event_list.events:
                granted.update(0x100 + int(i.operands[0]) for i in script.instructions if i.opcode == 0x21)
    assert not granted & set(CANDIDATE_INDICES), "an event script grants a candidate slot"
