"""Read-only locators for every L2BASM table: where each record starts and which entry points it has.

All tables are u16 entries relative to the table's own address, records sorted and packed right after the table.
Each reader takes the table address from the ``LDA long,X`` operand the game itself reads it through, so the readers
follow a table that a base patch moved (FRUE, Spekkio and Kureji move the monster table to 0x282000).
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import IO

from helpers.addresses import address_from_lorom
from tables import CapsuleObject, ItemObject, MonsterObject


MONSTER_HEADER_SIZE = 0x21
CAPSULE_HEADER_SIZE = 0x2B
CAPSULE_ATTACK_FIELD = 37
CAPSULE_REACTION_FIELD = 39
CAPSULE_BOUND = 0xBEE9F  # the shop pointer table follows the last capsule record
ITEM_FLAGS = 9  # bytes 9 and 10: which property words follow the 13-byte common block
ITEM_WORDS = 13
ITEM_SCRIPT_BITS = {"menu": 0, "battle": 1, "weapon": 2, "armor": 3}
SPELL_TABLE = 0xAFA5B
SPELL_COUNT = 40
SPELL_BOUND = 0xAFF16  # one past spell 39's script (a lone 00 at 0xAFF15)
SPELL_SCRIPT_FIELD = 0x11
IP_EFFECT_TABLE = 0xAF1EF
IP_EFFECT_COUNT = 141
SUBROUTINE_TABLE = 0xB7ADD
SUBROUTINE_COUNT = 41
SUBROUTINE_BOUND = 0xB8000  # end of bank $96

# File offset of each table's ``LDA long,X`` operand (the 3-byte LoROM address of the table).
TABLE_REFS = {
    "monster": 0xFB28,
    "item": 0xF29D,
    "subroutine": 0x2BDA3,
    "ip_effect": 0xF46E,
    "spell": 0xF451,
    "capsule": 0x143A3,
}


@dataclass(frozen=True)
class RecordSource:
    table: str
    index: int
    start: int
    bound: int
    entries: dict[str, int]
    script_start: int | None = None
    external: dict[str, int] = field(default_factory=dict)
    """Entry points outside the record's script area: past ``bound`` (code shared with other records) or before
    ``script_start`` (Spekkio hides code in some monster name fields). Kept as raw record-relative values; they
    aren't part of this record's script."""

    @classmethod
    def split(
        cls, table: str, index: int, start: int, bound: int, entries: dict[str, int], script_start: int | None = None,
    ) -> "RecordSource":
        """Build a source, moving entries that point outside the record into ``external``."""
        size = bound - start
        first = script_start or 0
        inside = {name: offset for name, offset in entries.items() if first <= offset < size}
        outside = {name: offset for name, offset in entries.items() if name not in inside}
        return cls(table, index, start, bound, inside, script_start, outside)


def _u16(source: IO[bytes], address: int) -> int:
    source.seek(address)
    return int.from_bytes(source.read(2), "little")


def table_starts(source: IO[bytes], table: int, count: int) -> list[int]:
    return [table + _u16(source, table + 2 * i) for i in range(count)]


def _bounds(source: IO[bytes], starts: list[int], last_bound: int) -> dict[int, int]:
    """End of each record: the next record start, else ``last_bound``.

    A record past ``last_bound`` (moved out of its table's packed region) ends at the next record after it, or at
    the next known table or bank end.
    """
    ordered = sorted(set(starts))
    bounds = {}
    for i, start in enumerate(ordered):
        nxt = ordered[i + 1] if i + 1 < len(ordered) else None
        if start < last_bound:
            bounds[start] = nxt if nxt is not None and nxt <= last_bound else last_bound
        else:
            bounds[start] = min(nxt, table_bound(source, start)) if nxt is not None else table_bound(source, start)
    return bounds


def table_address(source: IO[bytes], table: str) -> int:
    """Where ``table`` is in ``source``, read from the code that indexes it."""
    source.seek(TABLE_REFS[table])
    return address_from_lorom(int.from_bytes(source.read(3), "little"))


def table_bound(source: IO[bytes], address: int) -> int:
    """End of the last record: the next known table or boundary after ``address`` in its bank, else the bank end."""
    bank_end = (address // 0x8000 + 1) * 0x8000
    marks = [table_address(source, name) for name in TABLE_REFS] + [CAPSULE_BOUND, SPELL_BOUND, SUBROUTINE_BOUND]
    return min([mark for mark in marks if address < mark <= bank_end] + [bank_end])


def read_record(source: IO[bytes], rec: RecordSource) -> bytes:
    source.seek(rec.start)
    return source.read(rec.bound - rec.start)


def monster_header_size(record: bytes) -> tuple[int, dict[str, int]]:
    """Length of a monster record's header (fixed part, markers, 00) and its script entries."""
    pos = MONSTER_HEADER_SIZE
    entries: dict[str, int] = {}
    while record[pos] != 0x00:
        marker = record[pos]
        value = int.from_bytes(record[pos + 1 : pos + 3], "little")
        if marker == 0x07:  # noqa: PLR2004
            entries["attack"] = value
        elif marker == 0x08:  # noqa: PLR2004
            entries["defense"] = value
        elif marker != 0x03:  # noqa: PLR2004 (03 = item drop: item, rate)
            msg = f"Unknown monster record marker {marker:#04x} at +{pos:#x}."
            raise ValueError(msg)
        pos += 3
    return pos + 1, entries


def monster_records(source: IO[bytes]) -> list[RecordSource]:
    address = table_address(source, "monster")
    starts = table_starts(source, address, MonsterObject.count)
    bounds = _bounds(source, starts, table_bound(source, address))
    out = []
    for index, start in enumerate(starts):
        source.seek(start)
        record = source.read(bounds[start] - start)
        header, entries = monster_header_size(record)
        if entries:
            out.append(RecordSource.split("monster", index, start, bounds[start], entries, header))
    return out


def capsule_records(source: IO[bytes]) -> list[RecordSource]:
    address = table_address(source, "capsule")
    starts = table_starts(source, address, CapsuleObject.count)
    bounds = _bounds(source, starts, table_bound(source, address))
    return [
        RecordSource.split(
            "capsule",
            index,
            start,
            bounds[start],
            {"attack": _u16(source, start + CAPSULE_ATTACK_FIELD), "reaction": _u16(source, start + CAPSULE_REACTION_FIELD)},
            CAPSULE_HEADER_SIZE,
        )
        for index, start in enumerate(starts)
    ]


def item_script_words(flags: int) -> dict[str, int]:
    """Record offset of the property word holding each script's offset, for the scripts the flags announce."""
    return {
        name: ITEM_WORDS + 2 * (flags & ((1 << bit) - 1)).bit_count()
        for name, bit in ITEM_SCRIPT_BITS.items()
        if flags >> bit & 1
    }


def item_records(source: IO[bytes]) -> list[RecordSource]:
    address = table_address(source, "item")
    starts = table_starts(source, address, ItemObject.count)
    bounds = _bounds(source, starts, table_bound(source, address))
    out = []
    for index, start in enumerate(starts):
        flags = _u16(source, start + ITEM_FLAGS)
        entries = {name: _u16(source, start + word) for name, word in item_script_words(flags).items()}
        if entries:
            out.append(RecordSource.split("item", index, start, bounds[start], entries))
    return out


def spell_records(source: IO[bytes]) -> list[RecordSource]:
    address = table_address(source, "spell")
    starts = table_starts(source, address, SPELL_COUNT)
    bounds = _bounds(source, starts, table_bound(source, address))
    return [
        RecordSource.split("spell", index, start, bounds[start], {"effect": _u16(source, start + SPELL_SCRIPT_FIELD)})
        for index, start in enumerate(starts)
    ]


def ip_effect_records(source: IO[bytes]) -> list[RecordSource]:
    address = table_address(source, "ip_effect")
    starts = table_starts(source, address, IP_EFFECT_COUNT)
    bounds = _bounds(source, starts, table_bound(source, address))
    return [RecordSource("ip_effect", i, start, bounds[start], {"effect": 1}, 0) for i, start in enumerate(starts)]


def subroutine_records(source: IO[bytes], table: int | None = None) -> list[RecordSource]:
    address = table_address(source, "subroutine") if table is None else table
    starts = table_starts(source, address, SUBROUTINE_COUNT)
    bounds = _bounds(source, starts, table_bound(source, address))
    return [RecordSource("subroutine", i, start, bounds[start], {"body": 0}) for i, start in enumerate(starts)]


ALL_READERS: dict[str, Callable[[IO[bytes]], list[RecordSource]]] = {
    "monster": monster_records,
    "capsule": capsule_records,
    "item": item_records,
    "spell": spell_records,
    "ip_effect": ip_effect_records,
    "subroutine": subroutine_records,
}
