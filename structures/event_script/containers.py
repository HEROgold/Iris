"""Map-level containers: ``MapEvent`` (one per map) and ``EventList`` (one per event class).

Container byte layout (see 07_game_reference.md):

- ``MapEventObject`` record (``0x38010`` + ``index*8``): eventlist low/high, npc low/high, map-name
  pointer. The event-list block base is ``eventlists_pointer`` and the NPC-load script lives at
  ``npc_pointer`` (both 15-bit offsets from bank base ``0x38000``).
- Event-list block at ``eventlists_pointer``: 2-byte magic (``b"PH"``) then **six** 2-byte relative
  offsets, one per event class ``X A B C D E`` (``EventClass(0..5)``); the NPC-load list is a
  seventh, referenced separately by the map record.
- Each event list is a table of ``index(1), offset(2)`` entries terminated by ``0xFF``; each
  ``offset`` is relative to ``eventlists_pointer`` and locates a script's bytecode.

Frozen (unmodified) containers write their bytes back verbatim, giving byte-identity.
"""

import logging
from typing import Self

from _types.objects import Cache
from enums.event_scripts import EventClass
from helpers.files import read_file, restore_pointer, write_file
from helpers.name import read_as_decompressed_name
from logger import iris
from structures.event_script.script import EventScript
from tables import MapEventObject


log = logging.getLogger(f"{iris.name}.MapEvent")

EVENT_MAGIC = b"PH"
EVENT_LIST_COUNT = 6
EVENT_HEADER_SIZE = 2 + (EVENT_LIST_COUNT * 2)  # magic + six relative pointers

# Sentinels bounding the last script in each cluster (from terrorwave).
END_NPC_POINTER = 0x3AE4D
END_EVENT_POINTER = 0x7289E

_all_pointers: list[int] | None = None


class EventList:
    """A single event class's script table (``index, offset`` entries terminated by ``0xFF``)."""

    def __init__(self, base_pointer: int, offset: int, event_class: EventClass) -> None:
        self.base_pointer = base_pointer
        self.offset = offset
        self.pointer = base_pointer + offset
        self.event_class = event_class
        self.events: list[EventScript] = []
        self.raw_table = b""
        self.dirty = False
        self._gen_scripts()

    def __repr__(self) -> str:
        return f"EventList(pointer={self.pointer:#07x}, class={self.event_class.name}, scripts={len(self.events)})"

    @restore_pointer
    def _gen_scripts(self) -> None:
        if self.event_class is EventClass.NPC_SCRIPT:
            self.events.append(EventScript(self.base_pointer, self.offset, -1, self.event_class))
            return

        read_file.seek(self.pointer)
        start = self.pointer
        while True:
            index = read_file.read(1)[0]
            if index == 0xFF:
                break
            offset = int.from_bytes(read_file.read(2), "little")
            self.events.append(EventScript(self.base_pointer, offset, index, self.event_class))
        end = read_file.tell()
        read_file.seek(start)
        self.raw_table = read_file.read(end - start)

    def read(self, all_pointers: list[int]) -> None:
        for event in self.events:
            event.read(_next_pointer(all_pointers, event.pointer))

    def script_pointers(self) -> list[int]:
        return [event.pointer for event in self.events]

    def write(self) -> None:
        """Persist this list. Only a *dirty* table is rewritten; scripts persist themselves.

        A frozen (unmodified) table is left untouched -- it is already correct in the working ROM (a
        copy of the source), so re-writing it would be pointless and could clobber another patch's edit
        to this region. Every script's :meth:`EventScript.write` is still called so modified scripts get
        persisted (frozen scripts are no-ops there too).
        """
        if self.event_class is EventClass.NPC_SCRIPT:
            for event in self.events:
                event.write()
            return
        if self.dirty:
            write_file.seek(self.pointer)
            for event in self.events:
                offset = event.pointer - self.base_pointer
                if not 0 <= offset <= 0xFFFF:
                    msg = f"Event-list offset out of range: {offset:#x}"
                    raise ValueError(msg)
                write_file.write(bytes([event.index]))
                write_file.write(offset.to_bytes(2, "little"))
            write_file.write(b"\xff")
        for event in self.events:
            event.write()


class MapEvent:
    """The event container for one map: its event lists plus the NPC-load script."""

    _cache = Cache[int, Self]()

    def __init__(  # noqa: PLR0913
        self,
        pointer: int,
        eventlist_lowbytes: bytes,
        eventlist_highbyte: bytes,
        npc_lowbytes: bytes,
        npc_highbyte: bytes,
        map_name_offset: int,
    ) -> None:
        log.debug(f"Creating MapEvent from {pointer=:#08x}")
        self.pointer = pointer
        self._eventlist_lowbytes = eventlist_lowbytes
        self._eventlist_highbyte = eventlist_highbyte
        self._npc_lowbytes = npc_lowbytes
        self._npc_highbyte = npc_highbyte
        self._map_name_offset = map_name_offset
        self.address = MapEventObject.address
        self.index = 0
        self._magic = EVENT_MAGIC
        self._header_raw = b""
        self.event_lists: list[EventList] = []
        self._read = False
        self._gen_lists()

    def __repr__(self) -> str:
        return f"MapEvent(index={self.index:#04x}, pointer={self.pointer:#07x})"

    @classmethod
    def from_index(cls, index: int) -> Self:
        """Build (and cache) the map's container and parse all of its scripts."""
        inst = cls.from_table(MapEventObject.address, index)
        inst.read()
        return inst

    @classmethod
    def from_table(cls, address: int, index: int) -> Self:
        """Build (and cache) the map's container -- event-list tables only, scripts not yet parsed."""
        if inst := cls._cache.from_cache(index):
            return inst

        pointer = address + index * MapEventObject.size
        read_file.seek(pointer)
        inst = cls(
            pointer,
            read_file.read(MapEventObject.eventlist_lowbytes),
            read_file.read(MapEventObject.eventlist_highbyte),
            read_file.read(MapEventObject.npc_lowbytes),
            read_file.read(MapEventObject.npc_highbyte),
            int.from_bytes(read_file.read(MapEventObject.map_name_pointer), "little"),
        )
        inst.address = address
        inst.index = index
        cls._cache.to_cache(index, inst)
        return inst

    @restore_pointer
    def _gen_lists(self) -> None:
        read_file.seek(self.event_list_pointer)
        self._header_raw = read_file.read(EVENT_HEADER_SIZE)
        self._magic = self._header_raw[:2]
        if self._magic != EVENT_MAGIC:
            log.warning("Map %#04x: unexpected event magic %r (expected %r).", self.index, self._magic, EVENT_MAGIC)

        # NPC-load script (referenced by the map record, not by the six-pointer block).
        self.event_lists.append(EventList(self.base_pointer, self.npc_offset, EventClass.NPC_SCRIPT))

        for i in range(EVENT_LIST_COUNT):
            offset = int.from_bytes(self._header_raw[2 + i * 2 : 4 + i * 2], "little")
            self.event_lists.append(EventList(self.event_list_pointer, offset, EventClass(i)))

    def read(self) -> None:
        if self._read:
            return
        pointers = get_all_pointers()
        for event_list in self.event_lists:
            event_list.read(pointers)
        self._read = True

    @property
    def npc_script(self) -> EventScript:
        return self.event_lists[0].events[0]

    @property
    def base_pointer(self) -> int:
        base = self.pointer & 0xFF8000
        if base != 0x38000:
            log.warning("Map %#04x: unexpected base pointer %#07x.", self.index, base)
        return base

    @property
    def event_list_pointer(self) -> int:
        offset = int.from_bytes(self._eventlist_lowbytes, "little") | (int.from_bytes(self._eventlist_highbyte, "little") << 15)
        return self.base_pointer + offset

    @property
    def npc_offset(self) -> int:
        return int.from_bytes(self._npc_lowbytes, "little") | (int.from_bytes(self._npc_highbyte, "little") << 15)

    @property
    def npc_pointer(self) -> int:
        return self.base_pointer + self.npc_offset

    @property
    def map_name_pointer(self) -> int:
        return self.base_pointer + self._map_name_offset

    @property
    def map_name(self) -> bytes:
        return read_as_decompressed_name(self.map_name_pointer)

    @property
    def clean_map_name(self) -> bytes:
        return self.map_name.replace(b"\x0a", b"").replace(b"\x00", b"")

    def write(self) -> None:
        """Persist the map's event scripts. Only modified scripts (and dirty tables) are written.

        The map record and the event-list header are never mutated by this subsystem (no relocation is
        wired in), so they are left as-is in the working ROM rather than re-emitted verbatim -- that
        keeps the write confined to the scripts that actually changed and avoids clobbering other
        patches. If script relocation is added later, the record/header would need a dirty flag and
        would be written here.
        """
        for event_list in self.event_lists:
            event_list.write()


def _next_pointer(all_pointers: list[int], pointer: int) -> int:
    """Return the smallest known pointer strictly greater than ``pointer``."""
    for candidate in all_pointers:
        if candidate > pointer:
            return candidate
    return pointer + 0x8000


def get_all_pointers() -> list[int]:
    """Sorted set of every event-list, NPC and script pointer across all maps (plus END sentinels).

    Used to bound each script's byte range by the next known pointer (terrorwave's approach). Built
    once from every map's event-list tables (no script parsing, so no recursion) and cached.
    """
    global _all_pointers  # noqa: PLW0603
    if _all_pointers is not None:
        return _all_pointers

    pointers: set[int] = {END_NPC_POINTER, END_EVENT_POINTER}
    for index in range(MapEventObject.count):
        map_event = MapEvent.from_table(MapEventObject.address, index)
        pointers.add(map_event.event_list_pointer)
        pointers.add(map_event.npc_pointer)
        for event_list in map_event.event_lists:
            pointers.add(event_list.pointer)
            pointers.update(event_list.script_pointers())
    _all_pointers = sorted(pointers)
    return _all_pointers
