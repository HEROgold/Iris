"""Tests for the L2BASM builder helpers (``scripting.l2basm.helpers``), migrated from the old battle_builder tests.

The byte-exact cases below are real in-ROM scripts: four monster attack scripts (extracted from the vanilla
compendium) and four capsule attack/reaction scripts. Each asserts that the helpers assemble to the identical bytes
at the script's real record offset. Spells are stubbed to their L2BASM index so the suite is deterministic. Every
capsule record's round trip is in test_l2basm_roundtrip.py.
"""

from dataclasses import dataclass

import pytest

from errors import ScriptAssemblyError
from scripting.core import Instruction, Label
from scripting.l2basm.helpers import (
    Target,
    assemble_block,
    cast_spell,
    cast_spell_free,
    chance,
    choose,
    defend,
    display_name,
    end,
    execute,
    flee,
    goto,
    if_ge,
    label,
    on_chance,
    on_fail,
    physical_attack,
    raw,
    resist,
    sequence,
    set_reg,
    target,
)


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
    assert assemble_block(root, 0x28) == _hexbytes("32 01 28 01 32 01 28 00")


def test_monster_cyclops_chance_skip() -> None:
    root = sequence(
        target(Target.ONE_FOE),
        on_chance(0x10, "out"),
        physical_attack(),
        end(),
        label("out"),
    )
    assert assemble_block(root, 0x2B) == _hexbytes("32 01 05 10 33 00 28 00")


def test_monster_skull_lizard_cast_with_mp() -> None:
    root = sequence(
        target(Target.ONE_FOE),
        on_chance(0x40, "out"),
        cast_spell(_SpellStub(7)),  # Vortex
        on_fail("out"),
        end(),
        label("out"),
    )
    assert assemble_block(root, 0x2B) == _hexbytes("32 01 05 40 37 00 2C 07 04 37 00 00")


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
    assert assemble_block(root, 0x28) == _hexbytes("32 01 05 80 36 00 32 05 2C 04 04 36 00 00")


def test_capsule_reaction_status_immunity() -> None:
    root = sequence(resist(0x11), end())
    assert assemble_block(root, 0x4F) == _hexbytes("42 11 00 00")


def test_capsule_hard_hat_dispatcher() -> None:
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
    assert assemble_block(root, 0x2B, max_size=0x49 - 0x2B) == _hexbytes(expected)


def test_capsule_foomy_s_dispatcher() -> None:
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
    assert assemble_block(root, 0x2B, max_size=0x4F - 0x2B) == _hexbytes(expected)


# -- sugar & assembler behaviour --------------------------------------------------------------------


def test_inline_chance_jumps_past_body() -> None:
    # chance(p, body) runs body with prob p by jumping *past* it with prob 1-p.
    root = sequence(chance(0.5, physical_attack()))
    assert assemble_block(root, 0x00) == _hexbytes("05 80 05 00 28 00")


def test_choose_dispatch_then_blocks() -> None:
    root = choose(
        chance(0x30, cast_spell_free(_SpellStub(0x1E), target=Target.ALL_ALLIES)),
        chance(0xB0, cast_spell_free(_SpellStub(0x05), target=Target.ONE_FOE)),
        default=physical_attack(target=Target.ONE_FOE),
    )
    out = assemble_block(root, 0x2B, max_size=0x4F - 0x2B)
    # dispatch tests + default first, then one END-terminated block per branch.
    assert out.startswith(_hexbytes("05 30 37 00 05 B0 43 00 32 01 28 00"))
    assert out.endswith(_hexbytes("4F 00"))
    assert len(out) <= 0x4F - 0x2B


def test_assemble_appends_end_when_missing() -> None:
    assert assemble_block(sequence(physical_attack()), 0x00) == _hexbytes("28 00")


def test_on_chance_float_and_raw_int_agree() -> None:
    as_float = assemble_block(sequence(on_chance(0.5, "x"), end(), label("x")), 0x00)
    as_int = assemble_block(sequence(on_chance(0x80, "x"), end(), label("x")), 0x00)
    assert as_float == as_int


def test_max_size_overflow_raises() -> None:
    root = sequence(physical_attack(), physical_attack(), physical_attack(), end())
    with pytest.raises(ScriptAssemblyError, match="exceeds max_size"):
        assemble_block(root, 0x00, max_size=2)


def test_undefined_label_raises() -> None:
    with pytest.raises(ScriptAssemblyError, match="Undefined label"):
        assemble_block(sequence(on_chance(0x40, "nowhere"), end()), 0x00)


def test_inline_chance_shape_is_white_box_sane() -> None:
    items = sequence(chance(0.5, physical_attack()))
    assert isinstance(items[0], Instruction)
    assert items[0].opcode == 0x05
    assert isinstance(items[-1], Label)
    assert items[0].operands[1] == items[-1]


def test_assembling_at_another_origin_moves_only_jump_bytes() -> None:
    root = sequence(goto("tail"), raw(bytes([0x42, 0x11, 0x00])), label("tail"), resist(0x11), end(), label("out"))
    at_4f = assemble_block(root, 0x4F)
    at_5c = assemble_block(root, 0x5C)
    assert [i for i in range(len(at_4f)) if at_4f[i] != at_5c[i]] == [1]
    assert int.from_bytes(at_5c[1:3], "little") - int.from_bytes(at_4f[1:3], "little") == 0x5C - 0x4F


def test_cast_spell_free_bytes() -> None:
    assert assemble_block(cast_spell_free(_SpellStub(5)), 0) == bytes.fromhex("47 78 00 54 05 01 4F 00")
