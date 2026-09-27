"""Builder helpers for hand-written L2BASM. Every helper returns a list of items (a Block).

Ported from structures.battle_builder with the same names and byte output. ``block`` adds a missing END;
``assemble_block`` assembles a block on its own at a given origin.
"""

from dataclasses import dataclass
from enum import Enum
from itertools import count
from typing import TYPE_CHECKING, Protocol

from scripting.core import Data, Instruction, Item, Label, Script, assemble
from scripting.l2basm.opcodes import L2BASM


if TYPE_CHECKING:
    from collections.abc import Iterable


type Block = list[Item]

_label_ids = count()


class _HasIndex(Protocol):
    index: int


class Target(Enum):
    """``0x32`` targeting prefixes. ``ALL`` is the bare ``+all`` modifier that follows a base target."""

    ONE_FOE = (0x01,)
    SELF = (0x06,)
    ALL = (0x05,)
    ALL_FOES = (0x01, 0x05)
    ALL_ALLIES = (0x06, 0x05)


def _ins(opcode: int, *operands: object) -> Block:
    return [Instruction(opcode, list(operands))]


def _prob_byte(prob: float | int) -> int:  # noqa: PYI041 (float = ratio, int = raw byte)
    if isinstance(prob, float):
        if not 0.0 <= prob <= 1.0:
            msg = f"Float probability must be in [0, 1]: {prob}"
            raise ValueError(msg)
        return round(prob * 0xFF)
    if not 0 <= prob <= 0xFF:
        msg = f"Raw chance byte must be in [0, 255]: {prob}"
        raise ValueError(msg)
    return prob


def target(t: Target, items: Block | None = None) -> Block:
    prefix = [item for value in t.value for item in _ins(0x32, value)]
    return prefix if items is None else [*prefix, *items]


def _with_target(items: Block, t: Target | None) -> Block:
    return items if t is None else target(t, items)


def end() -> Block:
    return _ins(0x00)


def execute() -> Block:
    return _ins(0x01)


def physical_attack(target: Target | None = None) -> Block:
    return _with_target(_ins(0x28), target)


def defend(target: Target | None = None) -> Block:
    return _with_target(_ins(0x29), target)


def flee(target: Target | None = None) -> Block:
    return _with_target(_ins(0x2A), target)


def raw(data: bytes) -> Block:
    return [Data(bytes(data))]


def cast_spell(spell: _HasIndex, target: Target | None = None) -> Block:
    return _with_target(_ins(0x2C, spell.index), target)


def cast_spell_free(spell: _HasIndex, target: Target | None = None) -> Block:
    """``47 78 00 54 <idx> 01 4F``: cast without MP (capsule/IP route)."""
    return _with_target([*_ins(0x47, 0x78, 0x00), *_ins(0x54, spell.index), *_ins(0x01), *_ins(0x4F)], target)


def use_item(item: _HasIndex) -> Block:
    return _ins(0x2B, item.index)


def display_name(name_number: int, *, capsule: bool = True) -> Block:
    return _ins(0x3E if capsule else 0x1E, name_number & 0xFF)


def resist(index: int) -> Block:
    return _ins(0x42, index & 0xFF, 0x00)


def set_reg(reg: int, value: int) -> Block:
    return _ins(0x0C, reg & 0xFF, value)


def battle_anim(number: int) -> Block:
    return _ins(0x5A, number & 0xFF)


def apply_status(kind: int, prob: int) -> Block:
    return _ins(0x27, kind & 0xFF, prob & 0xFF)


def physical_damage(element: int, base: int, extra: int = 0) -> Block:
    return _ins(0x21, element, base, extra & 0xFF)


def magical_damage(element: int, base: int, extra: int = 0) -> Block:
    return _ins(0x22, element, base, extra & 0xFF)


def label(name: str) -> Block:
    return [Label(name)]


def goto(name: str) -> Block:
    return _ins(0x03, Label(name))


def on_chance(prob: float | int, name: str) -> Block:  # noqa: PYI041
    return _ins(0x05, _prob_byte(prob), Label(name))


def on_fail(name: str) -> Block:
    return _ins(0x04, Label(name))


def learnable(slot: int, name: str) -> Block:
    return _ins(0x3F, slot & 0xFF, Label(name))


def _compare(opcode: int, reg: int, value: int, name: str) -> Block:
    return _ins(opcode, reg & 0xFF, value, Label(name))


def if_eq(reg: int, value: int, name: str) -> Block:
    return _compare(0x06, reg, value, name)


def if_ne(reg: int, value: int, name: str) -> Block:
    return _compare(0x07, reg, value, name)


def if_gt(reg: int, value: int, name: str) -> Block:
    return _compare(0x08, reg, value, name)


def if_lt(reg: int, value: int, name: str) -> Block:
    return _compare(0x09, reg, value, name)


def if_ge(reg: int, value: int, name: str) -> Block:
    return _compare(0x0A, reg, value, name)


def if_le(reg: int, value: int, name: str) -> Block:
    return _compare(0x0B, reg, value, name)


@dataclass
class _Chance:
    """A probability paired with a body; ``sequence`` inlines it, ``choose`` makes it a branch."""

    prob: float | int
    body: Block


def chance(prob: float | int, body: Block) -> _Chance:  # noqa: PYI041
    return _Chance(prob, body)


def _inline(guard: _Chance) -> Block:
    skip = f"__chance_{next(_label_ids)}"
    jump = (1.0 - guard.prob) if isinstance(guard.prob, float) else (0xFF - guard.prob)
    return [*on_chance(jump, skip), *guard.body, Label(skip)]


def sequence(*parts: "Block | _Chance") -> Block:
    out: Block = []
    for part in parts:
        out.extend(_inline(part) if isinstance(part, _Chance) else part)
    return out


def choose(*branches: _Chance, default: Block) -> Block:
    if not branches:
        msg = "choose() needs at least one chance() branch."
        raise ValueError(msg)
    names = [f"__choose_{next(_label_ids)}" for _ in branches]
    tests = [item for branch, name in zip(branches, names, strict=True) for item in on_chance(branch.prob, name)]
    blocks = [
        item
        for branch, name in zip(branches, names, strict=True)
        for item in [Label(name), *branch.body, *end()]
    ]
    return [*tests, *default, *end(), *blocks]


def _ends_in_end(items: "Iterable[Item]") -> bool:
    for item in reversed(list(items)):
        if isinstance(item, Label):
            continue
        return isinstance(item, Instruction) and item.opcode == 0x00
    return False


def block(items: Block) -> Block:
    """``items`` with a terminating END added if the last non-label item isn't one."""
    return items if _ends_in_end(items) else [*items, *end()]


def ret() -> Block:
    """``43``: return from a $42 subroutine to the calling script."""
    return _ins(0x43)


def routine(items: Block) -> Block:
    """A $42 subroutine body: ``items`` with a terminating RETURN (``43``) added if the last item isn't one.

    Use this instead of ``block`` for subroutines: ``00`` there ends the calling script, not just the subroutine.
    """
    last = next((item for item in reversed(items) if not isinstance(item, Label)), None)
    return items if isinstance(last, Instruction) and last.opcode == 0x43 else [*items, *ret()]  # noqa: PLR2004


def assemble_block(items: Block, origin: int, *, max_size: int | None = None) -> bytes:
    return assemble(Script(L2BASM, block(items)), origin, max_size=max_size).data
