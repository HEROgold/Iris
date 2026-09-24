"""The node/token model for the L2BASM battle-script builder.

A :class:`Node` is anything that can ``emit`` a flat list of :data:`Token`. A token is a literal
byte (``int``), a zero-width :class:`Label` marker, or a :class:`Ref` jump placeholder that the
assembler later resolves to a 2-byte little-endian, *record-relative* offset
(``script.offset + position_of(label)``). This mirrors the event-script compiler's symbolic-label +
two-pass idiom (``structures/event_script/compiler.py``), the only other place Iris resolves local
jumps.

Everything here is the **low-level layer**: one constructor per L2BASM opcode plus the control-flow
primitives (labels, gotos, chances, compares). The high-level sugar (``cast_spell``, ``chance``,
``choose``, ``target``) lives in :mod:`structures.battle_builder.sugar` and is built on top of these.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable


if TYPE_CHECKING:
    from structures.item import Item
    from structures.spell import Spell


@dataclass(frozen=True)
class Label:
    """A zero-width marker naming a byte position within the assembled script."""

    name: str


@dataclass(frozen=True)
class Ref:
    """A 2-byte jump placeholder; resolves to ``script.offset + position_of(Label(name))``."""

    name: str


type Token = int | Label | Ref


@runtime_checkable
class Node(Protocol):
    """Anything that can emit a flat token stream (leaves emit ints; control flow emits Label/Ref)."""

    def emit(self) -> list[Token]: ...


@dataclass
class _Tokens:
    """A concrete :class:`Node` wrapping a fixed token list. All leaf constructors return one."""

    tokens: list[Token]

    def emit(self) -> list[Token]:
        return list(self.tokens)


def _u16(value: int) -> tuple[int, int]:
    if not 0 <= value <= 0xFFFF:
        msg = f"Value out of u16 range: {value:#x}"
        raise ValueError(msg)
    return (value & 0xFF, value >> 8)


def _prob_byte(prob: float | int) -> int:  # noqa: PYI041 (the int/float split is a runtime distinction)
    """A chance byte. ``float`` in ``[0, 1]`` scales to ``/255``; ``int`` in ``[0, 255]`` is raw."""
    if isinstance(prob, float):
        if not 0.0 <= prob <= 1.0:
            msg = f"Float probability must be in [0, 1]: {prob}"
            raise ValueError(msg)
        return round(prob * 0xFF)
    if not 0 <= prob <= 0xFF:
        msg = f"Raw chance byte must be in [0, 255]: {prob}"
        raise ValueError(msg)
    return prob


# -- terminators & simple actions -------------------------------------------------------------------


def end() -> _Tokens:
    """``00`` END -- terminates the current execution path."""
    return _Tokens([0x00])


def execute() -> _Tokens:
    """``01`` Execute -- run the effect so far and continue (multiple actions in one turn)."""
    return _Tokens([0x01])


def physical_attack() -> _Tokens:
    """``28`` Physical attack."""
    return _Tokens([0x28])


def defend() -> _Tokens:
    """``29`` Defend."""
    return _Tokens([0x29])


def flee() -> _Tokens:
    """``2A`` Flee/escape."""
    return _Tokens([0x2A])


def raw(data: bytes) -> _Tokens:
    """Escape hatch: emit raw bytes verbatim (no label support)."""
    return _Tokens(list(data))


# -- casting & items --------------------------------------------------------------------------------


def cast_spell(spell: "Spell") -> _Tokens:
    """``2C <idx>`` Cast a spell (consumes MP; monster AI). ``idx`` is ``spell.index``."""
    return _Tokens([0x2C, spell.index])


def cast_spell_free(spell: "Spell") -> _Tokens:
    """``47 78 00 54 <idx> 01 4F`` Cast a spell without consuming MP (capsule/IP route)."""
    return _Tokens([0x47, 0x78, 0x00, 0x54, spell.index, 0x01, 0x4F])


def use_item(item: "Item") -> _Tokens:
    """``2B <idx LE16>`` Use an item."""
    return _Tokens([0x2B, *_u16(item.index)])


# -- display / subroutines / registers --------------------------------------------------------------


def display_name(name_number: int, *, capsule: bool = True) -> _Tokens:
    """``3E <n>`` (capsule) or ``1E <n>`` (monster) -- display an attack name."""
    return _Tokens([0x3E if capsule else 0x1E, name_number & 0xFF])


def resist(index: int) -> _Tokens:
    """``42 <idx> 00`` Call a resistance/growth subroutine (e.g. ``0x11`` status immunity, ``0x25`` growth)."""
    return _Tokens([0x42, index & 0xFF, 0x00])


def set_reg(reg: int, value: int) -> _Tokens:
    """``0C <reg> <val LE16>`` Load ``value`` into L2BASM register ``reg``."""
    return _Tokens([0x0C, reg & 0xFF, *_u16(value)])


def battle_anim(number: int) -> _Tokens:
    """``5A <n>`` Play a battle animation."""
    return _Tokens([0x5A, number & 0xFF])


def apply_status(kind: int, prob: int) -> _Tokens:
    """``27 <kind> <prob>`` Apply a status effect (``prob`` out of ``0x64`` = 100%)."""
    return _Tokens([0x27, kind & 0xFF, prob & 0xFF])


def physical_damage(element: int, base: int, extra: int = 0) -> _Tokens:
    """``21 <elem LE16> <base LE16> <extra>`` Physical damage."""
    return _Tokens([0x21, *_u16(element), *_u16(base), extra & 0xFF])


def magical_damage(element: int, base: int, extra: int = 0) -> _Tokens:
    """``22 <elem LE16> <base LE16> <extra>`` Magical (INT-scaled, MP-free) damage."""
    return _Tokens([0x22, *_u16(element), *_u16(base), extra & 0xFF])


# -- control flow (label-aware) ---------------------------------------------------------------------


def label(name: str) -> _Tokens:
    """Mark a jump target; branches resolve to ``script.offset + this position``."""
    return _Tokens([Label(name)])


def goto(name: str) -> _Tokens:
    """``03 <ref>`` Unconditional jump to ``name``."""
    return _Tokens([0x03, Ref(name)])


def on_chance(prob: float | int, name: str) -> _Tokens:  # noqa: PYI041 (int = raw byte, float = ratio)
    """``05 <cc> <ref>`` Jump to ``name`` with probability ``cc/255``."""
    return _Tokens([0x05, _prob_byte(prob), Ref(name)])


def on_fail(name: str) -> _Tokens:
    """``04 <ref>`` Jump to ``name`` if the previous command failed."""
    return _Tokens([0x04, Ref(name)])


def learnable(slot: int, name: str) -> _Tokens:
    """``3F <slot> <ref>`` Jump to ``name`` if the capsule has learned learnable-attack ``slot``."""
    return _Tokens([0x3F, slot & 0xFF, Ref(name)])


# Compare opcodes: reg(1) value(2, LE) jumpOffset(2, LE). Jump when the comparison holds.
_COMPARES = {
    "if_eq": 0x06,
    "if_ne": 0x07,
    "if_gt": 0x08,
    "if_lt": 0x09,
    "if_ge": 0x0A,
    "if_le": 0x0B,
}


def _compare(opcode: int, reg: int, value: int, name: str) -> _Tokens:
    return _Tokens([opcode, reg & 0xFF, *_u16(value), Ref(name)])


def if_eq(reg: int, value: int, name: str) -> _Tokens:
    """``06`` Jump to ``name`` if ``reg == value``."""
    return _compare(_COMPARES["if_eq"], reg, value, name)


def if_ne(reg: int, value: int, name: str) -> _Tokens:
    """``07`` Jump to ``name`` if ``reg != value``."""
    return _compare(_COMPARES["if_ne"], reg, value, name)


def if_gt(reg: int, value: int, name: str) -> _Tokens:
    """``08`` Jump to ``name`` if ``reg > value``."""
    return _compare(_COMPARES["if_gt"], reg, value, name)


def if_lt(reg: int, value: int, name: str) -> _Tokens:
    """``09`` Jump to ``name`` if ``reg < value``."""
    return _compare(_COMPARES["if_lt"], reg, value, name)


def if_ge(reg: int, value: int, name: str) -> _Tokens:
    """``0A`` Jump to ``name`` if ``reg >= value``."""
    return _compare(_COMPARES["if_ge"], reg, value, name)


def if_le(reg: int, value: int, name: str) -> _Tokens:
    """``0B`` Jump to ``name`` if ``reg <= value``."""
    return _compare(_COMPARES["if_le"], reg, value, name)
