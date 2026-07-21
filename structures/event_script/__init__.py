"""Event-script subsystem: parse, dump, import and compile Lufia II event scripts.

See ``docs/event_scripts/`` for the full specification.
"""

from structures.event_script.containers import EventList, MapEvent
from structures.event_script.dump import dump_all, dump_map, parse_dump
from structures.event_script.instructions import Address, Instruction, TextChunk
from structures.event_script.manager import ZoneEventManager
from structures.event_script.script import EventScript


__all__ = [
    "Address",
    "EventList",
    "EventScript",
    "Instruction",
    "MapEvent",
    "TextChunk",
    "ZoneEventManager",
    "dump_all",
    "dump_map",
    "parse_dump",
]
