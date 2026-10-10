"""Locked doors and the key item each one needs (Iris-Dev#32).

A map's SETUP_MAP event list holds, at index 3, a list of 3-byte records ``object + 1, item (u16)`` ending in ``00``,
not a script. The field code (``$8E:B6D4``) looks the touched map object up there (via ``$80:C12E`` with A=3) and opens
the door only if the party holds the item (``$82:FB1F``). Vanilla has 23 such doors, every one gated by a key item.
"""

from dataclasses import dataclass

from iris.enums.event_scripts import EventClass
from iris.helpers.files import read_file
from iris.structures.event_script.containers import MapEvent
from iris.tables import MapEventObject


DOOR_LIST_INDEX = 3
"""The SETUP_MAP entry that holds door records instead of a script."""


@dataclass(frozen=True)
class KeyDoor:
    map_index: int
    map_object: int
    """The map object (NPC slot) that is the door."""
    item: int


def doors_on_map(map_index: int) -> list[KeyDoor]:
    event = MapEvent.from_index(map_index)
    setup = next(event_list for event_list in event.event_lists if event_list.event_class is EventClass.SETUP_MAP)
    doors: list[KeyDoor] = []
    for script in setup.events:
        if script.index != DOOR_LIST_INDEX:
            continue
        read_file.seek(script.pointer)
        while (record := read_file.read(3))[0] != 0:
            doors.append(KeyDoor(map_index, record[0] - 1, int.from_bytes(record[1:3], "little")))
    return doors


def key_doors() -> list[KeyDoor]:
    """Every locked door in the game, by map."""
    return [door for map_index in range(MapEventObject.count) for door in doors_on_map(map_index)]
