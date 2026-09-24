"""Pointer tables of u16 entries relative to the table itself, with their records packed after them.

Monsters, items, capsules, spells, IP effects and $42 subroutines all use this layout. ``write()`` uses the
cheapest step that works: in place, repack in place, move one record within the bank, or move the whole table.
"""

import logging
from collections.abc import Callable
from typing import IO, Protocol

from errors import CodeRefMismatch, NoFreeSpace, TableNotMovable
from helpers.files import write_file
from logger import iris
from rom_space.place import BytesBlock, Placement, PointerSite, U16Rel, place
from rom_space.pool import FreeSpace, bank_of, pool


log = logging.getLogger(f"{iris.name}.RomSpace.Table")


class TableRecord(Protocol):
    def build(self) -> bytes: ...


class Table:
    def __init__(  # noqa: PLR0913 (every argument is part of the table's definition)
        self,
        name: str,
        address: int,
        records: list[TableRecord],
        region_end: int,
        *,
        code_refs: list[PointerSite] | None = None,
        pinned: set[int] | None = None,
        movable: bool = False,
        make_room: Callable[[int], bool] | None = None,
        file: IO[bytes] | None = None,
        space: FreeSpace | None = None,
    ) -> None:
        self.name = name
        self.address = address
        self.records = records
        self.region_end = region_end
        self.code_refs = code_refs or []
        self.pinned = pinned or set()
        self.movable = movable
        self.make_room = make_room
        self._file = file
        self._space = space
        if space is not None:
            space.reserve(self.pinned)
        self._sizes: dict[int, int] = {}  # current length of records living outside the region
        self._vanilla_address = address

    @property
    def file(self) -> IO[bytes]:
        return write_file if self._file is None else self._file

    @property
    def space(self) -> FreeSpace:
        if self._space is None:
            self._space = pool()
            self._space.reserve(self.pinned)
        return self._space

    # -- reading the current layout ---------------------------------------------------------------------

    def entry_at(self, index: int) -> int:
        return self.address + 2 * index

    def starts(self) -> list[int]:
        self.file.seek(self.address)
        raw = self.file.read(2 * len(self.records))
        return [self.address + int.from_bytes(raw[2 * i : 2 * i + 2], "little") for i in range(len(self.records))]

    def _in_region(self, start: int) -> bool:
        return self.address <= start < self.region_end

    def _rooms(self, starts: list[int]) -> list[int]:
        inside = sorted({s for s in starts if self._in_region(s)})
        nxt = {s: (inside[i + 1] if i + 1 < len(inside) else self.region_end) for i, s in enumerate(inside)}
        return [nxt[s] - s if self._in_region(s) else self._sizes[s] for s in starts]

    def _current(self, start: int, size: int) -> bytes:
        self.file.seek(start)
        return self.file.read(size)

    # -- steps ------------------------------------------------------------------------------------------

    def write(self) -> str:
        built = [record.build() for record in self.records]
        starts = self.starts()
        if self._fits(built, starts) and all(
            self._current(s, room) == b + bytes(room - len(b))
            for s, b, room in zip(starts, built, self._rooms(starts), strict=True)
        ):
            return "unchanged"
        if self._fits(built, starts):
            self._in_place(built, starts)
            step = "in_place"
        elif self._can_repack(built):
            self._repack(built, starts)
            step = "repack"
        else:
            step = self._move_records(built, starts)
        self.file.flush()
        log.debug("%s: %s", self.name, step)
        return step

    def _fits(self, built: list[bytes], starts: list[int]) -> bool:
        return all(len(b) <= room for b, room in zip(built, self._rooms(starts), strict=True))

    def _in_place(self, built: list[bytes], starts: list[int]) -> None:
        for data, start, room in zip(built, starts, self._rooms(starts), strict=True):
            padded = data + bytes(room - len(data))
            if self._current(start, room) != padded:
                self.file.seek(start)
                self.file.write(padded)
            if not self._in_region(start):
                self._sizes[start] = len(data)

    def _first_record(self) -> int:
        return self.address + 2 * len(self.records)

    def _can_repack(self, built: list[bytes]) -> bool:
        if any(self._first_record() <= p < self.region_end for p in self.pinned):
            return False
        return sum(len(b) for b in built) <= self.region_end - self._first_record()

    def _repack(self, built: list[bytes], starts: list[int]) -> None:
        for start in starts:
            if not self._in_region(start):
                self.space.free(start, self._sizes.pop(start))
        pos = self._first_record()
        self.file.seek(self.address)
        for data in built:
            self.file.write((pos - self.address).to_bytes(2, "little"))
            pos += len(data)
        self.file.seek(self._first_record())
        packed = b"".join(built)
        self.file.write(packed + bytes(self.region_end - self._first_record() - len(packed)))

    def _move_records(self, built: list[bytes], starts: list[int]) -> str:
        rooms = self._rooms(starts)
        todo = [i for i, (b, room) in enumerate(zip(built, rooms, strict=True)) if len(b) > room]
        placements = [
            Placement(
                f"{self.name}[{i}]",
                BytesBlock(built[i]),
                None if self._in_region(starts[i]) else range(starts[i], starts[i] + rooms[i]),
                [PointerSite(self.entry_at(i), U16Rel(self.address))],
                bank=bank_of(self.address),
                force_move=True,
            )
            for i in todo
        ]
        try:
            new = self._place(placements)
        except NoFreeSpace:
            if self.make_room is None or not self.make_room(bank_of(self.address)):
                return self._move_table(built, starts)
            new = self._place(placements)
        for i, at in zip(todo, new, strict=True):
            if self._in_region(starts[i]):
                self.file.seek(starts[i])
                self.file.write(bytes(rooms[i]))
            self._sizes[at] = len(built[i])
        others = [i for i in range(len(built)) if i not in todo]
        self._in_place([built[i] for i in others], [starts[i] for i in others])
        return "move_record"

    def _place(self, placements: list[Placement]) -> list[int]:
        return place(placements, file=self.file, space=self.space)

    def _check_code_refs(self) -> None:
        for site in self.code_refs:
            self.file.seek(site.at)
            found = self.file.read(site.encoding.width)
            if found != site.value(self.address):
                msg = f"{self.name}: code ref at {site.at:#x} holds {found.hex()}, expected {site.value(self.address).hex()}."
                raise CodeRefMismatch(msg)

    def _move_table(self, built: list[bytes], starts: list[int]) -> str:
        if not self.movable:
            msg = f"{self.name} needs to move banks, but its code references aren't verified (movable=False)."
            raise TableNotMovable(msg)
        self._check_code_refs()
        header = bytearray()
        pos = 2 * len(built)
        for data in built:
            header += pos.to_bytes(2, "little")
            pos += len(data)
        block = BytesBlock(bytes(header) + b"".join(built))
        outside = [(s, self._sizes[s]) for s in starts if not self._in_region(s)]
        (new,) = self._place(
            [Placement(self.name, block, range(self.address, self.region_end), self.code_refs, force_move=True)]
        )
        for start, size in outside:
            self.space.free(start, size)
            del self._sizes[start]
        self.address = new
        self.region_end = new + block.size()
        return "move_table"

    def move(self) -> None:
        """Force step 4 (used to make room in a full bank)."""
        self._move_table([record.build() for record in self.records], self.starts())
