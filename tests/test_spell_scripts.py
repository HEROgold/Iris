"""Spell records on rom_space.Table: unchanged output, script edits, growth within bank $95."""

from collections.abc import Iterator
from copy import deepcopy

import pytest

from enums.patches import Patch
from errors import TableNotMovable
from helpers.files import original_file, write_file
from patcher import apply_patch
from rom_space.pool import bank_of, pool, reset_pool
from scripting.core import Instruction
from scripting.l2basm.edit import replace_entry
from scripting.l2basm.helpers import block, end, physical_attack, sequence
from scripting.l2basm.records import SPELL_COUNT, SPELL_SCRIPT_FIELD, SPELL_TABLE
from structures.spell import Spell, reset_spell_table, spell_table
from tests.reset_file import reset_file


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    reset_file()
    reset_pool()
    reset_spell_table()
    yield
    reset_file()
    reset_pool()
    reset_spell_table()


def _output() -> bytes:
    write_file.flush()
    write_file.seek(0)
    return write_file.read()


def _diff_offsets(a: bytes, b: bytes) -> list[int]:
    return [i for i, (x, y) in enumerate(zip(a, b, strict=False)) if x != y]


def test_every_spell_builds_its_vanilla_record() -> None:
    table = spell_table()
    rom = original_file.read_bytes()
    for record, start in zip(table.records, table.starts(), strict=True):
        data = record.build()  # type: ignore[attr-defined]
        assert rom[start : start + len(data)] == data, record


def test_script_offset_comes_from_the_effect_label() -> None:
    flash = Spell.from_index(0)
    assert flash.build()[SPELL_SCRIPT_FIELD : SPELL_SCRIPT_FIELD + 2] == (0x13).to_bytes(2, "little")


def test_unchanged_spells_write_nothing() -> None:
    for i in range(SPELL_COUNT):
        Spell.from_index(i).write()
    assert _output()[: len(original_file.read_bytes())] == original_file.read_bytes()


def test_flash_damage_edit_writes_only_that_operand() -> None:
    flash = Spell.from_index(0)
    damage = next(i for i in flash.code.body if isinstance(i, Instruction) and i.opcode == 0x22)  # noqa: PLR2004
    before = flash.build()
    damage.operands = [damage.operands[0], damage.operands[1] + 1, *damage.operands[2:]]  # type: ignore[operator]
    flash.write()
    changed = _diff_offsets(before, flash.build())
    assert len(changed) == 1
    start = spell_table().starts()[0]
    assert _diff_offsets(original_file.read_bytes(), _output()) == [start + changed[0]]


def test_header_edit_writes_only_the_header() -> None:
    flash = Spell.from_index(0)
    flash.mp_cost += 1
    flash.write()
    start = spell_table().starts()[0]
    assert set(_diff_offsets(original_file.read_bytes(), _output())) <= set(range(start, start + SPELL_SCRIPT_FIELD))


def test_writing_a_copy_writes_the_copy() -> None:
    copy = deepcopy(Spell.from_index(3))
    copy.price = 1234
    copy.write()
    reset_spell_table()
    assert Spell.from_index(3).price == 1234  # noqa: PLR2004


def test_growth_that_another_spell_frees_repacks_in_place() -> None:
    flash, bolt = Spell.from_index(0), Spell.from_index(1)
    replace_entry(bolt.code, "effect", block(sequence(end())))
    flash.code.body[-1:-1] = sequence(physical_attack(), physical_attack())
    assert spell_table().write() == "repack"
    assert spell_table().address == SPELL_TABLE
    starts = spell_table().starts()
    assert all(bank_of(start) == bank_of(SPELL_TABLE) for start in starts)
    assert Spell.reread(0).build() == flash.build()
    assert Spell.reread(1).build()[: len(bolt.build())] == bolt.build()
    assert spell_table().write() == "unchanged"  # a second write finds the repacked records


def test_growth_past_bank_95_needs_the_table_move() -> None:
    # Bank $95 has no verified free space after the spell table (its only zero run, 0xA8138, sits between two
    # pointer tables and before the table). Growth past the packed region waits for HER-198.
    flash = Spell.from_index(0)
    flash.code.body[-1:-1] = sequence(*[physical_attack()] * 40)
    pool()  # the first use expands the ROM; take the snapshot after that
    before = _output()
    with pytest.raises(TableNotMovable):
        flash.write()
    assert _output() == before


@pytest.mark.parametrize("base", [Patch.FRUE, Patch.SPEKKIO, Patch.KUREJI])
def test_unchanged_spells_write_nothing_on_each_base_patch(base: Patch) -> None:
    apply_patch(base)
    before = _output()
    assert spell_table().write() == "unchanged"
    assert _output() == before
