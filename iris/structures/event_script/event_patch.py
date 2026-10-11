"""Apply an event patch in terrorwave's format (``eventpatch_*.txt``, absynnonym's ``patch_game_script``).

A patch is a list of commands and ``EVENT`` blocks:

- ``!npc INDEX (MISC) MAP:X,Y`` adds or replaces an NPC position. ``X`` and ``Y`` are a tile or a
  ``LOW<=START<=HIGH`` range the NPC walks in (inclusive).
- ``!exit INDEX (MISC) MAP:X,Y->DEST:X,Y [WxH]`` adds or replaces an exit.
- ``!tile INDEX MAP:X,Y [WxH]`` adds or replaces a tile trigger.
- ``EVENT MAP-CLASS-INDEX`` followed by dump lines replaces that script, creating it when the map doesn't have it.

``INDEX`` is hex, or ``+1`` for the map's next free index. Everything after ``#`` is a comment.

The ``EVENT`` lines are Iris's own dump format (``dump.parse_dump``), with one difference: terrorwave's class
letters are one further along the alphabet. Its ``A`` is Iris's ``X`` (map setup), ``B`` is ``A``, ``C`` (talk
scripts) is ``B`` and ``D`` (tile scripts) is ``C``. ``X-XX`` is the NPC-load script in both.
"""

import re
from collections.abc import Iterable
from pathlib import Path

from iris.enums.event_scripts import EventClass
from iris.logger import iris
from iris.structures.event_script.containers import MapEvent, parse_all_map_events
from iris.structures.event_script.dump import parse_dump
from iris.structures.event_script.script import EventScript
from iris.structures.map_meta import MapMeta
from iris.structures.zone import NPC, Boundary, Exit, Tile, Zone


_TERRORWAVE_CLASSES = {letter: EventClass(value) for value, letter in enumerate("ABCDEF")}
_COMMENT = re.compile(r"#.*")
_EVENT = re.compile(r"^\s*EVENT\s+(\S+)")
SAME_MAP = 0xFF
"""An exit whose destination is its own map stores ``0xFF`` (terrorwave's ``add_exit``)."""


def apply_event_patch_file(path: Path) -> None:
    iris.debug(f"Applying event patch {path.name}")
    apply_event_patch(path.read_text(encoding="utf-8"))


def apply_event_patch(text: str) -> None:
    """Apply every command and script in ``text``, then write each map it touched."""
    parse_all_map_events()  # before any script changes: the text repair needs every map as it was
    maps: set[int] = set()
    script_lines: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = _COMMENT.sub("", raw_line).strip()
        if line.startswith("!"):
            maps.add(_apply_command(line.lower()))
            continue
        if event := _EVENT.match(raw_line):
            signature = event.group(1).upper()
            if signature in seen:
                msg = f"Event patch replaces {signature} twice."
                raise ValueError(msg)
            seen.add(signature)
            maps.add(int(signature.split("-")[0], 16))
        script_lines.append(raw_line)
    parse_dump("\n".join(script_lines), resolve=resolve_or_create)
    for map_index in sorted(maps):
        _write_map(map_index)


def resolve_or_create(signature: str) -> EventScript:
    """The script a terrorwave signature names, added to its map's event list when it doesn't exist yet."""
    map_text, letter, index_text = signature.upper().split("-")
    map_event = MapEvent.from_index(int(map_text, 16))
    if letter == "X":
        if index_text != "XX":
            msg = f"{signature}: the NPC-load script has no index (use X-XX)."
            raise ValueError(msg)
        return map_event.npc_script
    event_class = _TERRORWAVE_CLASSES[letter]
    index = int(index_text, 16)
    event_list = next(el for el in map_event.event_lists if el.event_class is event_class)
    for script in event_list.events:
        if script.index == index:
            return script
    script = EventScript(0, 0, index, event_class)
    script._read = True  # noqa: SLF001 -- brand new, nothing to read from ROM
    event_list.events.append(script)
    event_list.dirty = True
    return script


def _apply_command(line: str) -> int:
    command, *fields = line.split()
    if command == "!npc":
        return _apply_npc(*fields)
    if command == "!exit":
        return _apply_exit(*fields)
    if command == "!tile":
        return _apply_tile(*fields)
    msg = f"Unknown event patch command: {line}"
    raise ValueError(msg)


def _apply_npc(index_text: str, misc_text: str, location: str) -> int:
    map_text, coordinates = location.split(":")
    map_index = int(map_text, 16)
    x_text, y_text = coordinates.split(",")
    x, west, east = _axis(x_text)
    y, north, south = _axis(y_text)
    zone_data = Zone.from_index(map_index).data
    npcs = zone_data.npc_positions
    index = _index(index_text, (npc.index for npc in npcs), first=1)
    if not 1 <= index <= 0x20:
        msg = f"!npc on map {map_index:#04x}: index {index:#x} is outside 1..0x20."
        raise ValueError(msg)
    npc = NPC(index, x, y, Boundary(west, north, east, south), _misc(misc_text))
    zone_data.set_npcs(sorted([*(n for n in npcs if n.index != index), npc], key=lambda n: n.index))
    return map_index


def _apply_exit(index_text: str, misc_text: str, movement: str, dimensions: str = "1x1") -> int:
    source, destination = movement.split("->")
    source_text, source_location = source.split(":")
    destination_text, destination_location = destination.split(":")
    map_index = int(source_text, 16)
    destination_map = int(destination_text, 16)
    west, north = (int(value, 16) for value in source_location.split(","))
    destination_x, destination_y = (int(value, 16) for value in destination_location.split(","))
    width, height = (int(value) for value in dimensions.split("x"))
    zone_data = Zone.from_index(map_index).data
    exits = zone_data.exits
    index = _index(index_text, (exit_.index for exit_ in exits), first=0)
    new_exit = Exit(
        index,
        Boundary(west, north, west + width, north + height),
        _misc(misc_text),
        destination_x,
        destination_y,
        SAME_MAP if destination_map == map_index else destination_map,
    )
    zone_data.set_exits(sorted([*(e for e in exits if e.index != index), new_exit], key=lambda e: e.index))
    return map_index


def _apply_tile(index_text: str, location: str, dimensions: str = "1x1") -> int:
    if index_text == "+1":
        msg = f"!tile {location}: a tile needs an explicit index (its D-class script has the same index)."
        raise ValueError(msg)
    map_text, coordinates = location.split(":")
    map_index = int(map_text, 16)
    west, north = (int(value, 16) for value in coordinates.split(","))
    width, height = (int(value) for value in dimensions.split("x"))
    index = int(index_text, 16)
    zone_data = Zone.from_index(map_index).data
    tile = Tile(index, Boundary(west, north, west + width, north + height))
    zone_data.set_tiles(sorted([*(t for t in zone_data.tiles if t.index != index), tile], key=lambda t: t.index))
    return map_index


def _axis(text: str) -> tuple[int, int, int]:
    """``(position, low, high)`` for one ``!npc`` axis; ``high`` is exclusive, as stored."""
    if "<=" not in text:
        value = int(text, 16)
        return value, value, value + 1
    low, position, high = (int(value, 16) for value in text.split("<="))
    if not low <= position <= high:
        msg = f"!npc range {text}: the start is outside the range."
        raise ValueError(msg)
    return position, low, high + 1


def _misc(text: str) -> int:
    if not (text.startswith("(") and text.endswith(")")):
        msg = f"Malformed misc field {text!r}: expected (XX)."
        raise ValueError(msg)
    return int(text[1:-1], 16)


def _index(text: str, existing: Iterable[int], *, first: int) -> int:
    """An explicit hex index, or for ``+1`` one past the highest existing index (``first`` when there's none)."""
    if text != "+1":
        return int(text, 16)
    return max(existing, default=first - 1) + 1


def _write_map(map_index: int) -> None:
    zone = Zone.from_index(map_index)
    if zone.data.dirty:
        MapMeta.from_index(map_index).write()
    zone.write_events()
