"""Where a received ship appears: the world-map dock nearest each map (Iris-Dev#67).

key_items.asm places a Ship item that comes before the Treadool scene by writing a dock id to ``$09EE``; the game then
puts the ship at that dock the next time the world map loads (``$86:A2AE``, through the world map's dock section).
Items arrive in the field, inside a town or dungeon, where the game keeps no world-map position: leaving a map puts the
player at its exit's destination. So the base patch builds a table, one dock id per map, that key_items.asm indexes
with the current map (``$05AC``).

A map's world-map position is the destination of its first exit to the world map; a map without one (a castle floor,
a dungeon level) takes the position of the nearest map, by exits, that has one. Its dock is the world map's town dock
(ids ``$C8`` up) with the smallest squared distance to that position, on a world that wraps around at 256 tiles. Ties
go to the dock listed first. Maps that lead nowhere on the world map (the Ancient Cave) keep Treadool's dock.
"""

from collections import deque

from iris.structures.zone import ZoneData, zone_data_pointer
from iris.tables import MapMetaObject


WORLD_MAP = 0
DOCK_SECTION = 6
"""The world map ZoneData's dock section (header offset +$0E): ``[id, x, y]`` records, ``$FF``-terminated."""
DOCK_RECORD = 3
FIRST_TOWN_DOCK = 0xC8
"""Docks below this are the story's ship locations (7D(01) is Treadool's); the Warp list uses $C8 up."""
TREADOOL_DOCK = 0xD6
WORLD_SIZE = 256
"""The world map is 256x256 tiles and wraps around (the field code masks pixel positions with $0FFF)."""
TABLE_SIZE = 256
"""One entry per possible ``$05AC`` value, so the asm needs no bounds check."""
NO_MAP = 0xFF
"""Exit destination meaning "back where you came from", not a map."""

type Position = tuple[int, int]


def world_docks() -> dict[int, Position]:
    """The world map's town docks: id -> (x, y), in the order the game lists them."""
    section = _zone_data(WORLD_MAP).parsed_data[DOCK_SECTION]
    docks: dict[int, Position] = {}
    for i in range(0, len(section) - 1, DOCK_RECORD):
        dock, x, y = section[i : i + DOCK_RECORD]
        if dock >= FIRST_TOWN_DOCK:
            docks.setdefault(dock, (x, y))
    return docks


def world_positions() -> dict[int, Position]:
    """Map index -> the world-map tile its exits lead to, for every map that leads there."""
    exits = {index: _zone_data(index).exits for index in range(MapMetaObject.count)}
    positions: dict[int, Position] = {}
    for index, map_exits in exits.items():
        world_exit = next((exit_ for exit_ in map_exits if exit_.destination_map == WORLD_MAP), None)
        if index != WORLD_MAP and world_exit is not None:
            positions[index] = (world_exit.destination_x, world_exit.destination_y)
    # Breadth first from the maps that exit to the world map: each other map takes the position of the first one found.
    leads_to: dict[int, list[int]] = {index: [] for index in exits}
    for index, map_exits in exits.items():
        for exit_ in map_exits:
            if exit_.destination_map in leads_to and exit_.destination_map != NO_MAP:
                leads_to[exit_.destination_map].append(index)
    queue = deque(positions)
    while queue:
        index = queue.popleft()
        for source in leads_to[index]:
            if source != WORLD_MAP and source not in positions:
                positions[source] = positions[index]
                queue.append(source)
    return positions


def nearest_dock(position: Position, docks: dict[int, Position]) -> int:
    """The dock closest to ``position`` (squared distance, wrapping around the world; the first listed on a tie)."""

    def distance(dock: Position) -> int:
        dx, dy = (abs(a - b) for a, b in zip(position, dock, strict=True))
        return min(dx, WORLD_SIZE - dx) ** 2 + min(dy, WORLD_SIZE - dy) ** 2

    return min(docks, key=lambda dock: distance(docks[dock]))


def nearest_docks() -> bytes:
    """The dock id key_items.asm writes for each map index (Treadool's for maps with no world-map position)."""
    docks = world_docks()
    positions = world_positions()
    return bytes(nearest_dock(positions[index], docks) if index in positions else TREADOOL_DOCK for index in range(TABLE_SIZE))


def _zone_data(index: int) -> ZoneData:
    return ZoneData.from_pointer(zone_data_pointer(index))
