"""Backwards-compatibility shim.

The event-script engine now lives in the :mod:`structures.event_script` package; this module only
re-exports its public containers and keeps the small :class:`Event` (``EventInstObject``) mapping,
which links an event instance to a map zone. The retired opcode table, text codec and half-finished
readers that used to live here are preserved as documentation in ``docs/event_scripts/`` (see
``07_game_reference.md``) and reimplemented in the package.
"""

from typing import Self

from abc_.pointers import ReferencePointer
from helpers.bits import read_little_int
from helpers.files import read_file, restore_pointer, write_file
from structures.event_script import EventList, EventScript, MapEvent
from tables import EventInstObject


__all__ = ["Event", "EventList", "EventScript", "MapEvent"]


class Event(ReferencePointer):
    """An event instance: a 2-byte reference to a ``(zone_index, event_index)`` record."""

    _reference: int
    zone_index: int
    event_index: int

    @classmethod
    def from_index(cls, index: int) -> Self:
        return cls.from_reference(EventInstObject.address, index, EventInstObject.reference_pointer)

    @classmethod
    @restore_pointer
    def from_reference(cls, address: int, index: int, size: int) -> Self:
        inst = cls(address, index, size)
        read_file.seek(inst.pointer)
        inst._reference = read_little_int(read_file, 2)
        read_file.seek(inst._reference)
        inst.zone_index = read_little_int(read_file, 1)
        inst.event_index = read_little_int(read_file, 1)
        return inst

    def write(self) -> None:
        write_file.seek(self._reference)
        write_file.write(bytes([self.zone_index, self.event_index]))
