"""Write blocks of ROM data in place or move them, and rewrite every pointer that refers to them."""

import logging
from dataclasses import dataclass, field
from typing import IO, Protocol

from errors import PlacementVerifyError
from helpers.addresses import address_to_lorom
from helpers.files import write_file
from logger import iris
from rom_space.pool import FreeSpace, pool


log = logging.getLogger(f"{iris.name}.RomSpace.Place")


class Encoding(Protocol):
    width: int

    def encode(self, address: int) -> bytes: ...


@dataclass(frozen=True)
class U16Rel:
    """u16 relative to ``base`` (pointer tables, event lists)."""

    base: int
    width: int = 2

    def encode(self, address: int) -> bytes:
        return (address - self.base).to_bytes(2, "little")


@dataclass(frozen=True)
class Lorom24:
    """3-byte SNES LoROM address (ZoneData pointer table)."""

    width: int = 3

    def encode(self, address: int) -> bytes:
        return address_to_lorom(address).to_bytes(3, "little")


@dataclass(frozen=True)
class BankExtended15:
    """Map-record pointer: 15-bit low word, then a byte counting 32 KiB banks, relative to ``base``."""

    base: int
    width: int = 3

    def encode(self, address: int) -> bytes:
        offset = address - self.base
        return (offset & 0x7FFF).to_bytes(2, "little") + bytes([offset >> 15])


@dataclass(frozen=True)
class CodeLong:
    """Operand of a long-addressed instruction (``LDA $bbhhll,X``)."""

    width: int = 3

    def encode(self, address: int) -> bytes:
        return address_to_lorom(address).to_bytes(3, "little")


@dataclass(frozen=True)
class CodeAbs16:
    """16-bit immediate holding the low word of the SNES address (``ADC #$hhll``)."""

    width: int = 2

    def encode(self, address: int) -> bytes:
        return (address_to_lorom(address) & 0xFFFF).to_bytes(2, "little")


@dataclass(frozen=True)
class CodeBank:
    """8-bit immediate holding the SNES bank (``LDA #$bb``)."""

    width: int = 1

    def encode(self, address: int) -> bytes:
        return bytes([address_to_lorom(address) >> 16])


@dataclass(frozen=True)
class PointerSite:
    at: int
    encoding: Encoding
    delta: int = 0

    def value(self, address: int) -> bytes:
        return self.encoding.encode(address + self.delta)


class Block(Protocol):
    def size(self) -> int: ...
    def build(self, at: int) -> bytes: ...


@dataclass(frozen=True)
class BytesBlock:
    data: bytes

    def size(self) -> int:
        return len(self.data)

    def build(self, at: int) -> bytes:  # noqa: ARG002
        return self.data


@dataclass
class Placement:
    name: str
    block: Block
    old: range | None
    sites: list[PointerSite] = field(default_factory=list)
    bank: int | None = None
    near: int | None = None
    reach: int = 0xFFFF
    force_move: bool = False


def _target(p: Placement, space: FreeSpace) -> int:
    size = p.block.size()
    if p.old is not None and not p.force_move and size <= len(p.old):
        return p.old.start
    return space.alloc(size, bank=p.bank, near=p.near, reach=p.reach)


def place(placements: list[Placement], *, file: IO[bytes] | None = None, space: FreeSpace | None = None) -> list[int]:
    """Measure and allocate every placement, then write them all. Nothing is written if any allocation fails."""
    file = write_file if file is None else file
    space = pool() if space is None else space
    with space.plan():
        targets = [_target(p, space) for p in placements]
    for p, at in zip(placements, targets, strict=True):
        data = p.block.build(at)
        assert len(data) == p.block.size(), p.name
        moved = p.old is None or at != p.old.start
        if moved and p.old is not None:
            space.free(p.old.start, len(p.old))
        file.seek(at)
        file.write(data)
        if not moved and p.old is not None and len(data) < len(p.old):
            file.write(bytes(len(p.old) - len(data)))
        if moved:
            for site in p.sites:
                file.seek(site.at)
                file.write(site.value(at))
        file.flush()
        file.seek(at)
        if file.read(len(data)) != data:
            msg = f"{p.name}: bytes at {at:#x} differ after writing."
            raise PlacementVerifyError(msg)
        log.debug("%s: %s %s -> %#x (%d bytes)", p.name, "moved" if moved else "in place",
                  f"{p.old.start:#x}" if p.old else "new", at, len(data))
    return targets
