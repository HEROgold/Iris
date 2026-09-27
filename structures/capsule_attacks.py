"""Capsule attacks (CapAttacks): the records ``3E XX`` runs in battle and the SP menu lists, and adding new ones.

The game turns an attack index into its record with the routine at ``$81:F476``::

    ASL : TAX : LDA $97F63B,X : CLC : ADC #$F63B : RTL

Its one caller (``$81:AD51``) reads the record through ``[$0E]`` with the bank fixed to ``$97``. So every record
must sit in bank ``$97``, but the table itself can be anywhere: only the ``LDA`` operand says where it is. A record
is the attack's name number (``capsule_attack_names``), one byte that selects the animation (Inferno ``$82``,
Healing aura ``$2D``, physical attacks ``$F0``), then an L2BASM script in effect context: targeting, the effect,
then END, like Inferno's ``32 01 32 05 22 02 00 80 80 00 00``.

Vanilla packs the 84 records (``$00``-``$53``) right after the table, so the table can't grow in place.
:func:`write_capsule_attacks` writes a longer copy elsewhere and repoints the ``LDA`` operand. The existing records
and the ``ADC`` base stay where they are, and there's no bounds check to change.
"""

from helpers.addresses import address_from_lorom, address_to_lorom
from helpers.files import write_file
from rom_space.place import BytesBlock, CodeLong, Placement, PointerSite, place
from rom_space.pool import EXPANSION, bank_of
from scripting.l2basm.helpers import Block, assemble_block
from structures.capsule_attack_names import capsule_attack_names
from tables import CapAttackObject


TABLE_OPERAND = 0xF479
"""Operand of ``LDA $97F63B,X`` in ``$81:F476``: where the game reads the table."""
BASE_OPERAND = 0xF47E
"""Operand of ``ADC #$F63B`` in ``$81:F476``: every entry is relative to this address in bank ``$97``."""
RECORD_BANK = bank_of(0xB8000)
"""Bank ``$97`` (as a file bank for the pool), the only bank the caller reads records from."""
RECORD_BANK_SNES = 0x80 | RECORD_BANK
RECORD_HEADER = 2
"""Name number and animation byte before the script."""
BYTE_MAX = 0xFF

_count: int | None = None
_pending: list[bytes] = []


def _u(address: int, width: int) -> int:
    write_file.seek(address)
    return int.from_bytes(write_file.read(width), "little")


def table_address() -> int:
    """File offset of the table the game currently reads (vanilla ``0xBF63B``)."""
    return address_from_lorom(_u(TABLE_OPERAND, 3))


def count() -> int:
    """Number of attacks in the table, including ones appended but not written yet."""
    global _count  # noqa: PLW0603
    if _count is None:
        _count = CapAttackObject.count
    return _count + len(_pending)


def record_address(index: int) -> int:
    """File offset of attack ``index``'s record, resolved the way ``$81:F476`` does it."""
    base = _u(BASE_OPERAND, 2)
    entry = _u(table_address() + 2 * index, 2)
    snes = (RECORD_BANK_SNES << 16) | ((entry + base) & 0xFFFF)
    return address_from_lorom(snes)



def append_capsule_attack(name: str, animation: int, script: Block) -> int:
    """Add an attack named ``name`` and return its index, for ``3E XX`` or an SP-menu slot.

    ``script`` runs in effect context: it must target (``32 XX``) and end with END. It shouldn't jump; the record
    is placed after assembly and jump origins inside CapAttacks aren't confirmed. Nothing is written until
    :func:`write_capsule_attacks`.
    """
    if not 0 <= animation <= BYTE_MAX:
        msg = f"animation must be one byte, got {animation:#x}"
        raise ValueError(msg)
    number = capsule_attack_names.add(name)
    if number > BYTE_MAX:
        msg = f"attack name number {number} doesn't fit the record's name byte"
        raise ValueError(msg)
    record = bytes([number, animation]) + assemble_block(script, RECORD_HEADER)
    index = count()
    _pending.append(record)
    return index


def write_capsule_attacks() -> None:
    """Place the appended records in bank ``$97``, write the longer table, and repoint the game's lookup to it."""
    global _count  # noqa: PLW0603
    if not _pending:
        return
    old = count() - len(_pending)
    base = _u(BASE_OPERAND, 2)
    source = table_address()
    write_file.seek(source)
    entries = write_file.read(2 * old)

    starts = place([Placement(f"capsule attack {old + i}", BytesBlock(r), None, bank=RECORD_BANK)
                    for i, r in enumerate(_pending)])
    for start in starts:
        entries += (((address_to_lorom(start) & 0xFFFF) - base) & 0xFFFF).to_bytes(2, "little")
    # The table goes to the expansion area: bank $97 space is scarce and the records need it.
    table = Placement("capsule attack table", BytesBlock(entries), None, sites=[PointerSite(TABLE_OPERAND, CodeLong())],
                      near=EXPANSION.start, reach=len(EXPANSION))
    place([table])

    capsule_attack_names.write()
    _count = old + len(_pending)
    _pending.clear()


def reset_capsule_attacks() -> None:
    """Forget appended attacks and the cached count (tests reset the output between runs)."""
    global _count  # noqa: PLW0603
    _count = None
    _pending.clear()
