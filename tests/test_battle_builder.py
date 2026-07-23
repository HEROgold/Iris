"""Tests for the L2BASM battle-script builder (``structures.battle_builder``).

The byte-exact cases below are real in-ROM scripts: four monster attack scripts (extracted from the
vanilla compendium) and four capsule attack/reaction scripts (live dumps). Each asserts that the public
builder API assembles to the identical bytes at the script's real record offset. A stub with a single
``offset`` attribute is all :func:`assemble` needs; spells are stubbed to their L2BASM index so the
suite is deterministic and independent of the eager ``lookups`` import.
"""

from dataclasses import dataclass

import pytest

from structures.battle_builder import (
    Target,
    assemble,
    cast_spell,
    cast_spell_free,
    chance,
    choose,
    defend,
    display_name,
    end,
    execute,
    flee,
    if_ge,
    label,
    on_chance,
    on_fail,
    physical_attack,
    sequence,
    set_reg,
    target,
)
from structures.battle_builder.nodes import Label, Ref
from structures.battle_builder.sugar import _InlineChance  # pyright: ignore[reportPrivateUsage]


@dataclass
class _ScriptStub:
    offset: int


@dataclass
class _SpellStub:
    index: int


def _hexbytes(text: str) -> bytes:
    return bytes(int(part, 16) for part in text.split())


# -- byte-exact reproduction of real in-ROM scripts -------------------------------------------------


def test_monster_regal_goblin() -> None:
    root = sequence(
        physical_attack(target=Target.ONE_FOE),
        execute(),
        physical_attack(target=Target.ONE_FOE),
        end(),
    )
    assert assemble(_ScriptStub(0x28), root) == _hexbytes("32 01 28 01 32 01 28 00")


def test_monster_cyclops_chance_skip() -> None:
    root = sequence(
        target(Target.ONE_FOE),
        on_chance(0x10, "out"),
        physical_attack(),
        end(),
        label("out"),
    )
    assert assemble(_ScriptStub(0x2B), root) == _hexbytes("32 01 05 10 33 00 28 00")


def test_monster_skull_lizard_cast_with_mp() -> None:
    root = sequence(
        target(Target.ONE_FOE),
        on_chance(0x40, "out"),
        cast_spell(_SpellStub(7)),  # Vortex
        on_fail("out"),
        end(),
        label("out"),
    )
    assert assemble(_ScriptStub(0x2B), root) == _hexbytes("32 01 05 40 37 00 2C 07 04 37 00 00")


def test_monster_ork_mage_all_foe_cast() -> None:
    root = sequence(
        target(Target.ONE_FOE),
        on_chance(0x80, "out"),
        target(Target.ALL),
        cast_spell(_SpellStub(4)),  # Fireball
        on_fail("out"),
        end(),
        label("out"),
    )
    assert assemble(_ScriptStub(0x28), root) == _hexbytes("32 01 05 80 36 00 32 05 2C 04 04 36 00 00")


def test_capsule_reaction_status_immunity() -> None:
    from structures.battle_builder import resist  # noqa: PLC0415

    root = sequence(resist(0x11), end())
    assert assemble(_ScriptStub(0x4F), root) == _hexbytes("42 11 00 00")


def test_capsule_hard_hat_dispatcher() -> None:
    from structures.battle_builder import resist  # noqa: PLC0415

    root = sequence(
        set_reg(0x82, 0x0011),
        resist(0x25),
        if_ge(0x80, 0x8081, "flee"),
        on_chance(0x51, "hit"),
        on_chance(0x66, "hit"),
        display_name(0x14),
        end(),
        label("hit"), target(Target.ONE_FOE), physical_attack(), end(),
        label("flee"), flee(), end(),
    )
    expected = "0C 82 11 00 42 25 00 0A 80 81 80 47 00 05 51 43 00 05 66 43 00 3E 14 00 32 01 28 00 2A 00"
    assert assemble(_ScriptStub(0x2B), root, max_size=0x49 - 0x2B) == _hexbytes(expected)


def test_capsule_foomy_s_dispatcher() -> None:
    from structures.battle_builder import resist  # noqa: PLC0415

    root = sequence(
        set_reg(0x82, 0x0011),
        resist(0x25),
        if_ge(0x80, 0x8081, "flee"),
        on_chance(0x51, "hit"),
        on_chance(0x28, "defend"),
        on_chance(0x66, "hit"),
        display_name(0x00),
        end(),
        label("hit"), target(Target.ONE_FOE), physical_attack(), end(),
        label("defend"), defend(), end(),
        label("flee"), flee(), end(),
    )
    expected = (
        "0C 82 11 00 42 25 00 0A 80 81 80 4D 00 05 51 47 00 05 28 4B 00 05 66 47 00 3E 00 00 "
        "32 01 28 00 29 00 2A 00"
    )
    assert assemble(_ScriptStub(0x2B), root, max_size=0x4F - 0x2B) == _hexbytes(expected)


# -- sugar & assembler behaviour --------------------------------------------------------------------


def test_inline_chance_jumps_past_body() -> None:
    # chance(p, body) runs body with prob p by jumping *past* it with prob 1-p.
    root = sequence(chance(0.5, physical_attack()))
    assert assemble(_ScriptStub(0x00), root) == _hexbytes("05 80 05 00 28 00")


def test_choose_dispatch_then_blocks() -> None:
    root = choose(
        chance(0x30, cast_spell_free(_SpellStub(0x1E), target=Target.ALL_ALLIES)),
        chance(0xB0, cast_spell_free(_SpellStub(0x05), target=Target.ONE_FOE)),
        default=physical_attack(target=Target.ONE_FOE),
    )
    out = assemble(_ScriptStub(0x2B), root, max_size=0x4F - 0x2B)
    # dispatch tests + default first, then one END-terminated block per branch.
    assert out.startswith(_hexbytes("05 30 37 00 05 B0 43 00 32 01 28 00"))
    assert out.endswith(_hexbytes("4F 00"))
    assert len(out) <= 0x4F - 0x2B


def test_assemble_appends_end_when_missing() -> None:
    assert assemble(_ScriptStub(0x00), sequence(physical_attack())) == _hexbytes("28 00")


def test_on_chance_float_and_raw_int_agree() -> None:
    as_float = assemble(_ScriptStub(0x00), sequence(on_chance(0.5, "x"), end(), label("x")))
    as_int = assemble(_ScriptStub(0x00), sequence(on_chance(0x80, "x"), end(), label("x")))
    assert as_float == as_int


def test_max_size_overflow_raises() -> None:
    root = sequence(physical_attack(), physical_attack(), physical_attack(), end())
    with pytest.raises(ValueError, match="exceeds in-place footprint"):
        assemble(_ScriptStub(0x00), root, max_size=2)


def test_undefined_label_raises() -> None:
    with pytest.raises(ValueError, match="Undefined label"):
        assemble(_ScriptStub(0x00), sequence(on_chance(0x40, "nowhere"), end()))


def test_inline_chance_shape_is_white_box_sane() -> None:
    tokens = _InlineChance(chance(0.5, physical_attack())).emit()
    assert tokens[0] == 0x05
    assert isinstance(tokens[2], Ref)
    assert isinstance(tokens[-1], Label)
    assert tokens[2].name == tokens[-1].name
