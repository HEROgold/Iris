"""New capsule attacks (``structures.capsule_attacks``) resolve through the game's own lookup at ``$81:F476``.

Every check reads the output back with a small reader that does what the routine does: ``LDA table,X`` (the
operand at 0xF479 says where the table is), ``ADC #base`` (0xF47E), then read the record in bank ``$97``.
"""

from collections.abc import Iterator

import pytest

from helpers.files import original_file, write_file
from patches.HEROgold import foomy_s_firebird_valor
from rom_space.pool import reset_pool
from scripting.l2basm.helpers import Target, end, magical_damage, sequence, target
from structures.capsule import reset_capsule_table
from structures.capsule_attack_names import capsule_attack_names
from structures.capsule_attacks import append_capsule_attack, reset_capsule_attacks, write_capsule_attacks
from tests.reset_file import reset_file
from tests.reset_file import test_equal as files_equal


VANILLA_COUNT = 84
TABLE_OPERAND = 0xF479
BASE_OPERAND = 0xF47E
BANK_97 = range(0xB8000, 0xC0000)
TESTBOLT = bytes.fromhex("32 01 22 02 00 68 01 00 00")  # one foe, fire magical damage base 360, END


@pytest.fixture(autouse=True)
def _clean_output() -> Iterator[None]:
    for reset in (capsule_attack_names.unload, reset_file, reset_pool, reset_capsule_table, reset_capsule_attacks):
        reset()
    yield
    for reset in (capsule_attack_names.unload, reset_file, reset_pool, reset_capsule_table, reset_capsule_attacks):
        reset()


def _output() -> bytes:
    write_file.flush()
    write_file.seek(0)
    return write_file.read()


def _file(snes: int) -> int:
    return ((snes >> 16) & 0x7F) * 0x8000 + (snes & 0x7FFF)


def _record(rom: bytes, index: int) -> int:
    """File offset of attack ``index``, the way ``$81:F476`` and its caller find it."""
    table = _file(int.from_bytes(rom[TABLE_OPERAND:TABLE_OPERAND + 3], "little"))
    base = int.from_bytes(rom[BASE_OPERAND:BASE_OPERAND + 2], "little")
    entry = int.from_bytes(rom[table + 2 * index:table + 2 * index + 2], "little")
    return _file(0x970000 | ((entry + base) & 0xFFFF))


def _testbolt() -> list:
    return sequence(target(Target.ONE_FOE), magical_damage(0x0002, 0x0168), end())


def test_writing_with_nothing_appended_changes_nothing() -> None:
    write_capsule_attacks()
    files_equal()


def test_an_appended_attack_resolves_through_the_games_lookup() -> None:
    index = append_capsule_attack("Testbolt", 0x82, _testbolt())
    write_capsule_attacks()
    after = _output()

    assert index == VANILLA_COUNT
    record = _record(after, index)
    assert record in BANK_97
    number = after[record]
    assert after[record + 1:record + 2 + len(TESTBOLT)] == bytes([0x82]) + TESTBOLT
    capsule_attack_names.unload()
    assert capsule_attack_names[number] == "Testbolt"


def test_the_vanilla_attacks_keep_their_records() -> None:
    before = original_file.read_bytes()
    append_capsule_attack("Testbolt", 0x82, _testbolt())
    write_capsule_attacks()
    after = _output()

    assert after[BASE_OPERAND:BASE_OPERAND + 2] == before[BASE_OPERAND:BASE_OPERAND + 2]
    for index in range(VANILLA_COUNT):
        record = _record(before, index)
        assert _record(after, index) == record
        assert after[record:record + 16] == before[record:record + 16]


def test_a_second_write_extends_the_moved_table() -> None:
    first = append_capsule_attack("Testbolt", 0x82, _testbolt())
    write_capsule_attacks()
    second = append_capsule_attack("Testfire", 0x16, _testbolt())
    write_capsule_attacks()
    after = _output()

    assert (first, second) == (VANILLA_COUNT, VANILLA_COUNT + 1)
    assert after[_record(after, first) + 1] == 0x82
    assert after[_record(after, second) + 1] == 0x16
    assert _record(after, VANILLA_COUNT - 1) == _record(original_file.read_bytes(), VANILLA_COUNT - 1)


def test_an_animation_must_be_one_byte() -> None:
    with pytest.raises(ValueError, match="animation"):
        append_capsule_attack("Testbolt", 0x100, _testbolt())


def test_foomy_patch_adds_named_firebird_and_valor_attacks() -> None:
    foomy_s_firebird_valor()
    after = _output()
    capsule_attack_names.unload()

    firebird, valor = _record(after, 0x54), _record(after, 0x55)
    assert capsule_attack_names[after[firebird]] == "Firebird"
    assert capsule_attack_names[after[valor]] == "Valor"
    # Firebird: one foe, the spell's fire damage (base 360), no item-boost 57s, END.
    assert after[firebird + 1:firebird + 11] == bytes.fromhex("82 32 01 22 02 00 68 01 00 00")
    # Valor: all allies, then the spell's effect from 50 (may target the dead) to END.
    assert after[valor + 1:valor + 6] == bytes.fromhex("2D 32 06 32 05")
    assert after[valor + 6] == 0x50
