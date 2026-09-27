"""Monster records on rom_space.Table: unchanged output, attack edits, growth, Bolt Fish."""

from collections.abc import Iterator

import pytest

from enums.patches import Patch
from helpers.files import original_file, write_file
from patcher import apply_patch
from rom_space.pool import reset_pool
from scripting.core import Label, assemble
from scripting.l2basm.edit import reachable
from scripting.l2basm.helpers import cast_spell, end, label, on_chance, physical_attack, sequence
from scripting.l2basm.records import MONSTER_HEADER_SIZE
from structures import subroutine
from structures.monster import Monster, monster_table, reset_monster_table
from tables import MonsterObject
from tests.reset_file import reset_file


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    reset_file()
    reset_pool()
    subroutine.reset()
    reset_monster_table()
    yield
    reset_file()
    reset_pool()
    subroutine.reset()
    reset_monster_table()


def _output() -> bytes:
    write_file.flush()
    write_file.seek(0)
    return write_file.read()


class _Spell:
    index = 5


def test_every_monster_builds_its_vanilla_record() -> None:
    table = monster_table()
    rom = original_file.read_bytes()
    for record, start in zip(table.records, table.starts(), strict=True):
        data = record.build()
        assert rom[start : start + len(data)] == data, record


def test_writing_every_monster_unchanged_keeps_the_rom() -> None:
    for index in range(MonsterObject.count):
        Monster.from_index(index).write()
    assert _output()[: len(original_file.read_bytes())] == original_file.read_bytes()


def test_growing_an_attack_script_moves_the_record_and_keeps_the_others(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subroutine, "SUBROUTINES_MOVABLE", True)
    rom = original_file.read_bytes()
    table = monster_table()
    before = table.starts()
    jelly = Monster.from_index(0xA4)
    jelly.replace_attack(sequence(on_chance(0x80, "spell"), physical_attack(), end(), label("spell"),
                                  cast_spell(_Spell()), physical_attack(), physical_attack(), end()))
    jelly.write()
    after = table.starts()
    index = table.records.index(jelly)
    reread = Monster.reread(0xA4)
    assert reread.build() == jelly.build()
    for i, (old, new) in enumerate(zip(before, after, strict=True)):
        if i != index and old == new:
            size = len(table.records[i].build())
            assert _output()[new : new + size] == rom[old : old + size]


def test_attack_offset_points_at_the_attack_label() -> None:
    fish = Monster.from_index(85)  # Bolt Fish: attack and defense
    record = fish.build()
    out = assemble(fish.code, fish.code_start)  # type: ignore[arg-type]
    assert int.from_bytes(record[0x22:0x24], "little") == fish.code_start + out.labels["attack"]


def test_fix_boltfish_writes_the_same_bytes_as_before() -> None:
    from patches.HEROgold import fix_boltfish  # noqa: PLC0415

    fish_start = monster_table().starts()[85]
    vanilla = bytearray(original_file.read_bytes()[fish_start : fish_start + 0x51])
    vanilla[0x28 + 0x15] = 0x45  # the old patch: two self-jumps (+0x3B) of the handler now go to +0x45
    vanilla[0x28 + 0x1A] = 0x45
    fix_boltfish()
    assert _output()[fish_start : fish_start + 0x51] == bytes(vanilla)


@pytest.mark.parametrize("base", [Patch.FRUE, Patch.SPEKKIO, Patch.KUREJI])
def test_unchanged_monsters_write_nothing_on_each_base_patch(base: Patch) -> None:
    apply_patch(base)
    before = _output()
    assert monster_table().write() == "unchanged"
    assert _output() == before


def _defense_offset(record: bytes) -> int | None:
    pos = MONSTER_HEADER_SIZE
    while record[pos] != 0x00:
        if record[pos] == 0x08:  # noqa: PLR2004
            return int.from_bytes(record[pos + 1 : pos + 3], "little")
        pos += 3
    return None


def _shares_blocks(monster: Monster) -> bool:
    code = monster.code
    return (
        code is not None
        and set(monster._entries()) == {"attack", "defense"}  # noqa: SLF001
        and bool(reachable(code, "attack") & reachable(code, "defense"))
    )


def test_growing_a_defense_script_points_08_at_the_defense_label(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subroutine, "SUBROUTINES_MOVABLE", True)
    fish = Monster.from_index(85)  # Bolt Fish: attack and defense
    start = monster_table().starts()[85]
    fish.replace_script("defense", sequence(*[physical_attack()] * 12, end()))  # 13 bytes, the old defense has 7
    fish.write()
    assert monster_table().starts()[85] != start
    reread = Monster.reread(85)
    record = reread.build()
    out = assemble(reread.code, reread.code_start)  # type: ignore[arg-type]
    assert _defense_offset(record) == reread.code_start + out.labels["defense"]
    assert record == fish.build()


def test_adding_a_defense_script_writes_an_08_marker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subroutine, "SUBROUTINES_MOVABLE", True)
    index = next(i for i in range(MonsterObject.count) if Monster.from_index(i)._entries() == ["attack"])  # noqa: SLF001
    monster = Monster.from_index(index)
    monster.replace_script("defense", sequence(physical_attack(), end()))
    monster.write()
    reread = Monster.reread(index)
    assert reread._entries() == ["attack", "defense"]  # noqa: SLF001
    assert _defense_offset(reread.build()) is not None
    assert reread.build() == monster.build()


def test_defense_edit_keeps_blocks_attack_uses() -> None:
    shared = next(i for i in range(MonsterObject.count) if _shares_blocks(Monster.from_index(i)))
    monster = Monster.from_index(shared)
    assert monster.code is not None
    kept = [monster.code.body[i] for i in sorted(reachable(monster.code, "attack"))]
    monster.replace_script("defense", sequence(physical_attack(), end()))
    assert [monster.code.body[i] for i in sorted(reachable(monster.code, "attack"))] == kept
