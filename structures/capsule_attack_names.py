"""The capsule attack-name table: the text of the SP list and of every CapAttack's name number.

Layout (``CapAttackNameObject``): at ``address``, one u16 offset per name, relative to ``address``; the
names are null-terminated ASCII strings. Vanilla packs 78 names directly after the offsets, and FRUE
retranslates them, so the table is always read from the per-seed output (``write_file``), never from the
original ROM. The game looks names up by index only, so the table can grow as long as every name stays
inside the bank.
"""

from dataclasses import dataclass

from helpers.files import write_file
from helpers.free_space import MARGIN, free_runs
from tables import CapAttackNameObject


_GAP = MARGIN
"""Largest zero gap still counted as part of the table's footprint."""


@dataclass
class _Span:
    start: int
    end: int


class CapsuleAttackNames:
    """Read, extend, and (only when changed) write the capsule attack-name table.

    Loading is lazy: the table is read from the output the first time it is used (so a base patch applied
    after construction is seen), and ``unload()`` drops it so the next use reads it again.

    Writing keeps the offsets at the table address and packs the names right after them, within the
    table's own footprint (offsets plus names as currently laid out). Names that no longer fit go
    first-fit into free runs of the same bank; previous overflow blocks are zeroed first. The footprint is
    re-derived from the ROM on every read, so zero bytes left at its end after a spill are not reclaimed:
    the table can shrink its in-place room slightly but never writes outside what it owns.
    """

    def __init__(self) -> None:
        self.address = CapAttackNameObject.address
        self.bank_end = CapAttackNameObject.bank_end
        self.dirty = False
        self._names: list[bytes] = []
        self._footprint_end = self.address
        self._overflow: list[_Span] = []
        self._loaded = False

    def unload(self) -> None:
        """Forget the table (and any unsaved change); the next use reads it from the output again."""
        self._names = []
        self._overflow = []
        self._loaded = False
        self.dirty = False

    def _load(self) -> None:
        if not self._loaded:
            self.reload()

    def reload(self) -> None:
        """Discard unsaved changes and read the table from the output ROM."""
        write_file.flush()
        offsets: list[int] = []
        while not offsets or 2 * len(offsets) < min(offsets):
            offsets.append(self._u16(self.address + 2 * len(offsets)))
        spans: list[_Span] = []
        self._names = []
        for offset in offsets:
            start = self.address + offset
            name = self._read_string(start)
            self._names.append(name)
            spans.append(_Span(start, start + len(name) + 1))
        self._footprint_end, self._overflow = self._layout(self.address + 2 * len(offsets), spans)
        self._loaded = True
        self.dirty = False

    def __len__(self) -> int:
        self._load()
        return len(self._names)

    def __getitem__(self, index: int) -> str:
        self._load()
        return self._names[index].decode("ascii")

    def add(self, name: str) -> int:
        """Append ``name`` and return its name number (the index CapAttack records refer to)."""
        if not name or "\x00" in name or not name.isascii():
            msg = f"Capsule attack name must be non-empty ASCII without NUL bytes: {name!r}"
            raise ValueError(msg)
        self._load()
        self._names.append(name.encode("ascii"))
        self.dirty = True
        return len(self._names) - 1

    def write(self) -> None:
        """Write the table if it was loaded and changed since; otherwise do nothing."""
        if not self.dirty:
            return
        table_size = 2 * len(self._names)
        strings = [name + b"\x00" for name in self._names]
        if self.address + table_size > self._footprint_end:
            msg = f"{len(self._names)} name offsets no longer fit the table footprint at {self.address:#x}."
            raise ValueError(msg)

        for span in self._overflow:
            write_file.seek(span.start)
            write_file.write(bytes(span.end - span.start))

        positions: list[int] = []
        cursor = self.address + table_size
        for string in strings:
            if cursor + len(string) > self._footprint_end:
                break
            positions.append(cursor)
            cursor += len(string)
        in_place = len(positions)
        overflow = self._place_overflow(strings[in_place:], positions)

        write_file.seek(self.address)
        write_file.write(b"".join((p - self.address).to_bytes(2, "little") for p in positions))
        write_file.write(b"".join(strings[:in_place]))
        write_file.write(bytes(self._footprint_end - cursor))
        write_file.flush()

        self._overflow = overflow
        self.dirty = False
        written = list(self._names)
        self.reload()
        if self._names != written:
            msg = "Capsule attack-name table did not persist."
            raise ValueError(msg)

    def _place_overflow(self, strings: list[bytes], positions: list[int]) -> list[_Span]:
        """Pack ``strings`` first-fit into free runs of the bank, appending each address to ``positions``."""
        if not strings:
            return []
        write_file.flush()
        runs = [list(run) for run in free_runs(write_file, self.address, self.bank_end)]
        placed: list[_Span] = []
        for string in strings:
            run = next((r for r in runs if r[1] - r[0] >= len(string)), None)
            if run is None:
                msg = f"No free space in bank for capsule attack name {string[:-1]!r}."
                raise ValueError(msg)
            write_file.seek(run[0])
            write_file.write(string)
            positions.append(run[0])
            placed.append(_Span(run[0], run[0] + len(string)))
            run[0] += len(string)
        return placed

    @staticmethod
    def _layout(table_end: int, spans: list[_Span]) -> tuple[int, list[_Span]]:
        """Split name spans into the table's footprint and the blocks that live elsewhere.

        The footprint runs from the offsets through every name reachable with gaps of less than
        ``_GAP`` bytes (FRUE pads its retranslated names with 1-4 zero bytes). Anything further away is an
        overflow block, which Iris only writes at least ``MARGIN`` (16) bytes from other data.
        """
        footprint_end = table_end
        rest: list[_Span] = []
        for span in sorted(spans, key=lambda s: s.start):
            if table_end <= span.start < footprint_end + _GAP:
                footprint_end = max(footprint_end, span.end)
            elif rest and span.start < rest[-1].end + _GAP:
                rest[-1].end = max(rest[-1].end, span.end)
            else:
                rest.append(_Span(span.start, span.end))
        return footprint_end, rest

    @staticmethod
    def _u16(address: int) -> int:
        write_file.seek(address)
        return int.from_bytes(write_file.read(2), "little")

    @staticmethod
    def _read_string(address: int) -> bytes:
        write_file.seek(address)
        out = bytearray()
        while (byte := write_file.read(1)) not in (b"", b"\x00"):
            out += byte
        return bytes(out)


capsule_attack_names = CapsuleAttackNames()
"""The table instance patches edit. ``CapsuleMonster.write()`` calls its ``write()``, which only writes when
something was added since it was loaded."""
