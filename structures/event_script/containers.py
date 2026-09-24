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
        self.dirty = False
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

    def mark_dirty(self) -> None:
        """Flag the whole container (record, header, every table and script) for rewriting on :meth:`write`."""
        self.dirty = True
        for event_list in self.event_lists:
            event_list.dirty = True
            for script in event_list.events:
                script.dirty = True

    def write(self) -> None:
        """Persist the map's event scripts.

        The common case (no dirty script overflows its original slot) writes exactly as before:
        only modified scripts/tables move, the map record and event-list header stay untouched.
        When a dirty script *would* overflow, the in-place path cannot serve it (EventScript.write
        would raise), so the whole container relocates as one unit instead -- see write_relocated.
        The map record and the event-list header are otherwise only re-emitted when this container is
        ``dirty`` (see :meth:`mark_dirty`).
        """
        if self._needs_relocation():
            self.write_relocated()
            return
        if self.dirty:
            self._write_record()
            self._write_header()
        for event_list in self.event_lists:
            event_list.write()

    def _needs_relocation(self) -> bool:
        """True if any dirty script's recompiled bytes would overflow its original slot."""
        from structures.event_script.compiler import compile_script  # noqa: PLC0415

        for event_list in self.event_lists:
            for event in event_list.events:
                if not event.dirty:
                    continue
                if len(compile_script(event, ignore_pointers=True)) > len(event.raw):
                    return True
        return False

    def write_relocated(self) -> None:
        """Rebuild and relocate this map's ENTIRE event container as one unit, then repoint it.

        Moves the event-list header, all six event lists' script tables, every one of their
        scripts, and the NPC-load script together -- not just the dirty ones. Once the container
        moves, a "frozen" script's old bytes no longer exist anywhere its table (now elsewhere)
        still points to, so everything must be re-emitted at its new address, exactly as
        ``structures.zone.ZoneData.write_relocated`` rebuilds the whole ZoneData blob rather than
        patching one section in place.

        Layout: the whole container (14-byte header + six tables + every script's compiled bytes +
        the NPC script) is allocated as **one** contiguous, bank-local block via
        ``helpers.freespace.event_script_allocator``. Staying within a single 32KB bank keeps every
        event-list table offset (checked against ``0..0xFFFF`` by ``EventList.write``) comfortably
        in range for free, since a bank is half that span.

        Every ``Address`` operand a successfully-parsed script can contain is local (script-relative,
        ``instructions.Address`` raises at parse time on anything else -- see its docstring), so
        recompiling at a new address is purely mechanical: byte length never depends on where a
        script ends up (``compiler.compile_script``'s ``ignore_pointers`` pass proves this), so
        layout can be decided before any address is known, then everything recompiled for real once
        it is.
        """
        from helpers.freespace import event_script_allocator  # noqa: PLC0415
        from structures.event_script.compiler import compile_script  # noqa: PLC0415

        class_lists = self.event_lists[1:]  # index 0 is NPC_SCRIPT; these are EventClass(0..5)
        npc_script = self.npc_script

        # Pass 1: compiled length only -- address-independent, so this can run before layout exists.
        # Keyed by id(): EventScript.__eq__/__hash__ are defined over base_pointer/offset, which
        # pass 2 below mutates, so the objects themselves are not stable dict keys past this point.
        lengths: dict[int, int] = {}
        for event_list in class_lists:
            for event in event_list.events:
                lengths[id(event)] = len(compile_script(event, ignore_pointers=True))
        lengths[id(npc_script)] = len(compile_script(npc_script, ignore_pointers=True))

        table_sizes = [len(event_list.events) * 3 + 1 for event_list in class_lists]
        total_size = EVENT_HEADER_SIZE + sum(table_sizes) + sum(lengths.values())
        header_base = event_script_allocator.allocate(total_size)

        # Pass 2: assign every final address now that the full layout size is known.
        cursor = header_base + EVENT_HEADER_SIZE
        table_addresses: list[int] = []
        for size in table_sizes:
            table_addresses.append(cursor)
            cursor += size
        for event_list, table_address in zip(class_lists, table_addresses, strict=True):
            event_list.base_pointer = header_base
            for event in event_list.events:
                event.base_pointer = header_base
                event.pointer = cursor
                event.offset = cursor - header_base
                cursor += lengths[id(event)]
            event_list.pointer = table_address
            event_list.offset = table_address - header_base
        # The NPC script's OWN base_pointer must stay header_base, like every other script here:
        # compile_script resolves its local Address operands as a plain 16-bit value relative to
        # base_pointer, unrelated to the MapEventObject record's separate bank-extended encoding
        # (Pass 6 below) -- using the fixed, far-away 0x38000 base here (matching how the *record*
        # locates the script) blows that 16-bit encoding once the script sits ~header_base away
        # from 0x38000, i.e. exactly the case relocation into freespace always creates.
        npc_script.base_pointer = header_base
        npc_script.pointer = cursor
        npc_script.offset = cursor - header_base
        self.event_lists[0].base_pointer = header_base
        self.event_lists[0].pointer = npc_script.pointer
        self.event_lists[0].offset = npc_script.offset

        # Pass 3: write every event-list table now that addresses are final.
        for event_list, table_address in zip(class_lists, table_addresses, strict=True):
            write_file.seek(table_address)
            for event in event_list.events:
                offset = event.pointer - event_list.base_pointer
                if not 0 <= offset <= 0xFFFF:
                    msg = f"Event-list offset out of range: {offset:#x}"
                    raise ValueError(msg)
                write_file.write(bytes([event.index]))
                write_file.write(offset.to_bytes(2, "little"))
            write_file.write(b"\xff")
            event_list.dirty = False

        # Pass 4: recompile (now that base_pointer/pointer are final, so local Address operands
        # resolve correctly) and write every script, dirty or not.
        for script in [event for event_list in class_lists for event in event_list.events] + [npc_script]:
            data = compile_script(script, script_pointer=script.pointer)
            script.raw = data
            script.dirty = False
            # Scripts are packed with zero slack in the new layout (see docstring); a later
            # in-place edit's overflow check (EventScript.write's `_slot_size`) must reflect that,
            # not whatever slack the script happened to have at its old, pre-relocation address.
            script._slot_size = len(data)  # noqa: SLF001 -- this method IS EventScript's relocator
            write_file.seek(script.pointer)
            write_file.write(data)

        # Pass 5: write the event-list header (magic + six offsets from header_base).
        write_file.seek(header_base)
        write_file.write(EVENT_MAGIC)
        for event_list in class_lists:
            write_file.write((event_list.pointer - header_base).to_bytes(2, "little"))
        self._header_raw = EVENT_MAGIC + b"".join(
            (event_list.pointer - header_base).to_bytes(2, "little") for event_list in class_lists
        )

        # Pass 6: repoint this map's MapEventObject record to the new header/NPC locations.
        eventlist_offset = header_base - self.base_pointer
        npc_offset = npc_script.pointer - self.base_pointer
        self._eventlist_lowbytes, self._eventlist_highbyte = _encode_bank_extended_offset(eventlist_offset)
        self._npc_lowbytes, self._npc_highbyte = _encode_bank_extended_offset(npc_offset)
        self._write_record()
        self.dirty = False

    def _write_record(self) -> None:
        write_file.seek(self.pointer)
        write_file.write(self._eventlist_lowbytes)
        write_file.write(self._eventlist_highbyte)
        write_file.write(self._npc_lowbytes)
        write_file.write(self._npc_highbyte)
        write_file.write(self._map_name_offset.to_bytes(MapEventObject.map_name_pointer, "little"))

    def _write_header(self) -> None:
        write_file.seek(self.event_list_pointer)
        write_file.write(self._magic)
        for event_list in self.event_lists[1:]:  # [0] is the NPC-load script, referenced by the record
            write_file.write(event_list.offset.to_bytes(2, "little"))


def _encode_bank_extended_offset(offset: int) -> tuple[bytes, bytes]:
    """Encode an offset for a ``MapEventObject`` low/high pointer pair (inverse of the decode in
    ``MapEvent.event_list_pointer``/``npc_offset``: ``lowbytes | highbyte << 15``).

    The low field holds bits 0-14 and the high byte extends from bit 15, so the two must not
    overlap: bit 15 of the 2-byte low field is always written as 0, giving a clean OR on decode
    (equivalent to plain addition) up to an ~8MB range -- ample for a 4MB ROM.
    """
    if offset >> 23:
        msg = f"Offset {offset:#x} too large to encode in a MapEventObject low/high pointer pair."
        raise ValueError(msg)
    low = offset & 0x7FFF
    high = (offset >> 15) & 0xFF
    return low.to_bytes(2, "little"), bytes([high])


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
