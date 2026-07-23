"""High-level sugar for the battle-script builder, built on the low-level nodes.

These compose :mod:`structures.battle_builder.nodes` leaves into readable intent:
``cast_spell(Spells.DROWSY, target=Target.ONE_FOE)``, ``chance(0.5, ...)`` (independent inline guard),
``choose(...)`` (ordered mutual-exclusion dispatch). Targeting can be attached either as a ``target=``
kwarg on an action or via the :func:`target` combinator wrapping a block.
"""

from dataclasses import dataclass, field
from enum import Enum
from itertools import count
from typing import TYPE_CHECKING

from structures.battle_builder.nodes import Label, Node, Token, on_chance
from structures.battle_builder.nodes import cast_spell as _cast_spell
from structures.battle_builder.nodes import cast_spell_free as _cast_spell_free
from structures.battle_builder.nodes import defend as _defend
from structures.battle_builder.nodes import end as _end
from structures.battle_builder.nodes import flee as _flee
from structures.battle_builder.nodes import physical_attack as _physical_attack


if TYPE_CHECKING:
    from structures.spell import Spell


# Monotonic id source for auto-generated internal labels (chance/choose blocks). Label *names* only
# need to be unique within one assembled script, which a per-process counter guarantees.
_label_ids = count()


class Target(Enum):
    """``0x32`` targeting prefixes. ``ALL`` is the bare ``+all`` modifier (follows a base target)."""

    ONE_FOE = (0x32, 0x01)
    SELF = (0x32, 0x06)
    ALL = (0x32, 0x05)
    ALL_FOES = (0x32, 0x01, 0x32, 0x05)
    ALL_ALLIES = (0x32, 0x06, 0x32, 0x05)


@dataclass
class _Raw:
    """A :class:`Node` wrapping a fixed token list."""

    tokens: list[Token]

    def emit(self) -> list[Token]:
        return list(self.tokens)


@dataclass
class _Prefix:
    """Prefix ``node``'s emission with fixed ``prefix`` tokens (used for ``target``)."""

    prefix: list[Token]
    node: Node

    def emit(self) -> list[Token]:
        return [*self.prefix, *self.node.emit()]


@dataclass
class _Chance:
    """Marker pairing a probability with a body; consumed by :func:`sequence`/:func:`choose`."""

    prob: float | int
    body: Node


@dataclass
class _InlineChance:
    """A bare :func:`chance` used directly in a sequence: run the body with prob ``p``, else skip it."""

    inner: _Chance

    def emit(self) -> list[Token]:
        skip = f"__chance_{next(_label_ids)}"
        prob = self.inner.prob
        # Jump *past* the body when the roll fails, so the body runs inline with probability `prob`.
        jump_prob = (1.0 - prob) if isinstance(prob, float) else (0xFF - prob)
        return [*on_chance(jump_prob, skip).emit(), *self.inner.body.emit(), Label(skip)]


def _as_node(item: "Node | _Chance") -> Node:
    return _InlineChance(item) if isinstance(item, _Chance) else item


@dataclass
class _Seq:
    """A :class:`Node` that concatenates its children (bare ``chance`` children become inline guards)."""

    children: list[Node] = field(default_factory=list)

    def emit(self) -> list[Token]:
        out: list[Token] = []
        for child in self.children:
            out.extend(child.emit())
        return out


def sequence(*nodes: "Node | _Chance") -> _Seq:
    """Concatenate ``nodes``; a bare :func:`chance` child becomes an inline guard."""
    return _Seq([_as_node(n) for n in nodes])


def _target_tokens(t: Target) -> list[Token]:
    return list(t.value)


def target(t: Target, node: Node | None = None) -> Node:
    """Emit ``t``'s ``0x32`` bytes; as a combinator, prefix ``node`` so one target covers the block."""
    if node is None:
        return _Raw(_target_tokens(t))
    return _Prefix(_target_tokens(t), node)


def _with_target(node: Node, tgt: Target | None) -> Node:
    return node if tgt is None else _Prefix(_target_tokens(tgt), node)


def cast_spell(spell: "Spell", target: Target | None = None) -> Node:
    """Cast ``spell`` (consumes MP), optionally after a ``target`` prefix."""
    return _with_target(_cast_spell(spell), target)


def cast_spell_free(spell: "Spell", target: Target | None = None) -> Node:
    """Cast ``spell`` without consuming MP (capsule/IP route), optionally after a ``target`` prefix."""
    return _with_target(_cast_spell_free(spell), target)


def physical_attack(target: Target | None = None) -> Node:
    """Physical attack, optionally after a ``target`` prefix."""
    return _with_target(_physical_attack(), target)


def defend(target: Target | None = None) -> Node:
    """Defend, optionally after a ``target`` prefix."""
    return _with_target(_defend(), target)


def flee(target: Target | None = None) -> Node:
    """Flee, optionally after a ``target`` prefix."""
    return _with_target(_flee(), target)


def chance(prob: float | int, node: Node) -> _Chance:  # noqa: PYI041
    """A probability-guarded action.

    Used **inline** (directly inside a ``sequence``): runs ``node`` with probability ``prob``, else
    falls through -- independent of any sibling ``chance``. Used **inside** :func:`choose`: becomes an
    ordered, mutually-exclusive branch. ``prob`` is a float in ``[0, 1]`` or a raw int chance byte.
    """
    return _Chance(prob, node)


def choose(*branches: _Chance, default: Node) -> Node:
    """Ordered mutual-exclusion: roll each branch in turn; first hit runs its block and ends; else ``default``.

    Emits the ``0x05`` dispatch tests first, then ``default`` + END, then each branch block (each ended
    with its own END) at a label the dispatch jumps to. Reproduces the foomy attack-script shape.
    """
    if not branches:
        msg = "choose() needs at least one chance() branch."
        raise ValueError(msg)
    names = [f"__choose_{next(_label_ids)}" for _ in branches]
    tests: list[Token] = []
    for branch, name in zip(branches, names, strict=True):
        tests.extend(on_chance(branch.prob, name).emit())
    blocks: list[Token] = []
    for branch, name in zip(branches, names, strict=True):
        blocks.append(Label(name))
        blocks.extend(branch.body.emit())
        blocks.extend(_end().emit())
    return _Raw([*tests, *default.emit(), *_end().emit(), *blocks])
