"""Tests for the L2BASM battle-script builder (``structures.battle_builder``).

The byte-exact cases below are real in-ROM scripts: four monster attack scripts (extracted from the
vanilla compendium) and four capsule attack/reaction scripts (live dumps). Each asserts that the public
builder API assembles to the identical bytes at the script's real record offset. A stub with a single
``offset`` attribute is all :func:`assemble` needs; spells are stubbed to their L2BASM index so the
suite is deterministic and independent of the eager ``lookups`` import.
"""

from dataclasses import dataclass

import pytest

from helpers.files import original_file, write_file
from structures.battle_builder import (
    Node,
    Target,
    apply,
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
    goto,
    if_eq,
    if_ge,
    if_gt,
    if_le,
    if_lt,
    if_ne,
    label,
    learnable,
    on_chance,
    on_fail,
    physical_attack,
    raw,
    resist,
    sequence,
    set_reg,
    target,
)
from structures.battle_builder.nodes import Label, Ref
from structures.battle_builder.sugar import _InlineChance  # pyright: ignore[reportPrivateUsage]
from structures.battlescript import BattleScript, op_codes
from structures.capsule import CapsuleMonster
from tables import CapsuleObject
from tests.reset_file import reset_file
from tests.reset_file import test_equal as files_equal


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


# -- round trip against the real ROM: all 70 capsule attack/reaction scripts ------------------------


_JUMPS = {0x03: 0, 0x04: 0, 0x05: 1, 0x06: 3, 0x07: 3, 0x08: 3, 0x09: 3, 0x0A: 3, 0x0B: 3, 0x3F: 1}
_COMPARE_NODES = {0x06: if_eq, 0x07: if_ne, 0x08: if_gt, 0x09: if_lt, 0x0A: if_ge, 0x0B: if_le}
_CAPSULE_SCRIPTS = [(i, kind) for i in range(CapsuleObject.count) for kind in ("attack", "reaction")]


def _script(index: int, kind: str) -> BattleScript:
    capsule = CapsuleMonster.from_index(index)
    script = capsule.attack_script if kind == "attack" else capsule.reaction_script
    assert script is not None
    return script


def _instructions(script: BattleScript) -> list[tuple[int, bytes]]:
    """Linear decode of ``script.bytecode`` as (record-relative offset, instruction bytes)."""
    out, pos = [], 0
    code = script.bytecode
    while pos < len(code):
        size = 1 + op_codes[code[pos]]["params"]
        out.append((script.offset + pos, code[pos:pos + size]))
        pos += size
    return out


def _decompile(script: BattleScript) -> Node:
    """Rebuild a script from builder nodes: control flow becomes labels/refs, the rest known leaves or raw."""
    instructions = _instructions(script)
    labels: dict[int, str] = {}
    for _, ins in instructions:
        if ins[0] in _JUMPS:
            k = 1 + _JUMPS[ins[0]]
            target = int.from_bytes(ins[k:k + 2], "little")
            labels[target] = f"L{target:x}"
    nodes = []
    for off, ins in instructions:
        if off in labels:
            nodes.append(label(labels.pop(off)))
        op = ins[0]
        if op in _JUMPS:
            k = 1 + _JUMPS[op]
            name = f"L{int.from_bytes(ins[k:k + 2], 'little'):x}"
            if op == 0x03:
                nodes.append(goto(name))
            elif op == 0x04:
                nodes.append(on_fail(name))
            elif op == 0x05:
                nodes.append(on_chance(ins[1], name))
            elif op == 0x3F:
                nodes.append(learnable(ins[1], name))
            else:
                nodes.append(_COMPARE_NODES[op](ins[1], int.from_bytes(ins[2:4], "little"), name))
        elif op == 0x00:
            nodes.append(end())
        elif op == 0x0C:
            nodes.append(set_reg(ins[1], int.from_bytes(ins[2:4], "little")))
        elif op == 0x42:
            nodes.append(resist(ins[1]))
        elif op == 0x3E:
            nodes.append(display_name(ins[1]))
        elif op == 0x28:
            nodes.append(physical_attack())
        elif op == 0x29:
            nodes.append(defend())
        elif op == 0x2A:
            nodes.append(flee())
        else:
            nodes.append(raw(ins))
    # Every remaining label must sit exactly one past the last instruction (the "out" idiom).
    tail = script.offset + len(script.bytecode)
    assert set(labels) <= {tail}, f"jump targets outside the script: {sorted(map(hex, labels))}"
    nodes.extend(label(name) for name in labels.values())
    return sequence(*nodes)


def _rom_bytes(script: BattleScript) -> bytes:
    return original_file.read_bytes()[script.pointer:script.pointer + len(script.bytecode)]


@pytest.mark.parametrize(("index", "kind"), _CAPSULE_SCRIPTS)
def test_capsule_script_bytecode_is_the_contiguous_rom_span(index: int, kind: str) -> None:
    script = _script(index, kind)
    assert script.bytecode == _rom_bytes(script)


def test_capsule_learnable_branch_blocks_are_read() -> None:
    # Foomy M: ``3F 02 69 00`` jumps to +0x69, a block reachable only through that learnable branch.
    script = _script(1, "attack")
    assert dict(_instructions(script))[0x69] == _hexbytes("05 A3 4F 00")


@pytest.mark.parametrize(("index", "kind"), _CAPSULE_SCRIPTS)
def test_capsule_script_round_trips_through_the_builder(index: int, kind: str) -> None:
    script = _script(index, kind)
    assert assemble(script, _decompile(script)) == _rom_bytes(script)


def test_capsule_scripts_write_back_unchanged() -> None:
    for index, kind in _CAPSULE_SCRIPTS:
        _script(index, kind).write()
    files_equal()


def test_apply_rereads_what_it_wrote_to_the_output() -> None:
    script = _script(0, "attack")
    root = sequence(physical_attack(target=Target.ONE_FOE), end(), raw(bytes(0x4F - 0x2B - 4)))
    expected = assemble(script, root)
    try:
        apply(script, root, max_size=0x4F - 0x2B)
        write_file.flush()
        write_file.seek(script.pointer)
        assert write_file.read(len(expected)) == expected
        # the re-read walks the *output*: the new script is 4 reachable bytes, not the vanilla dispatcher.
        assert script.bytecode == expected[:4]
    finally:
        reset_file()


def test_rebase_jumps_moves_targets_inside_the_script() -> None:
    from structures.battle_builder import assemble_at  # noqa: PLC0415
    from structures.battlescript import rebase_jumps  # noqa: PLC0415

    root = sequence(goto("tail"), raw(bytes([0x42, 0x11, 0x00])), label("tail"), resist(0x11), end(), label("out"))
    assert rebase_jumps(assemble_at(0x4F, root), 0x4F, 0x5C) == assemble_at(0x5C, root)


def test_rebase_jumps_keeps_targets_outside_the_script() -> None:
    from structures.battlescript import rebase_jumps  # noqa: PLC0415

    code = bytes.fromhex("03 10 00 00")  # GoTo +0x10, which is before the script
    assert rebase_jumps(code, 0x4F, 0x5C) == code
