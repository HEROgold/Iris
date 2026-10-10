"""IP effect scripts on rom_space.Table: unchanged output, edits, moves, appending an effect."""

from collections.abc import Iterator

import pytest

from enums.patches import Patch
from errors import TableNotMovable
from helpers.files import original_file, write_file
from patcher import apply_patch
from rom_space.pool import pool, reset_pool
from scripting.core import Data, Label, Script, assemble
from scripting.l2basm import L2BASM
from scripting.l2basm.edit import replace_entry
from scripting.l2basm.helpers import block, end, physical_attack, sequence
from scripting.l2basm.records import IP_EFFECT_COUNT, IP_EFFECT_TABLE
from structures import ip_effect
from structures.ip_attack import IPAttack
from structures.ip_effect import IP_EFFECT_CODE_REFS, IPEffect, append_ip_effect, ip_effect_table, reset_ip_effect_table
from tables import IPAttackObject
from tests.reset_file import reset_file


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    reset_file()
    reset_pool()
    reset_ip_effect_table()
    yield
    reset_file()
    reset_pool()
    reset_ip_effect_table()


def _output() -> bytes:
    write_file.flush()
    write_file.seek(0)
    return write_file.read()


def _labels(script: Script) -> set[str]:
    return {item.name for item in script.body if isinstance(item, Label)}


def test_every_ip_effect_builds_its_vanilla_bytes() -> None:
    table = ip_effect_table()
    rom = original_file.read_bytes()
    assert len(table.records) == IP_EFFECT_COUNT
    for record, start in zip(table.records, table.starts(), strict=True):
        data = record.build()  # type: ignore[attr-defined]
        assert data[0] == 0xFF  # noqa: PLR2004
        assert rom[start : start + len(data)] == data, record


def test_unchanged_ip_effects_write_nothing() -> None:
    assert ip_effect_table().write() == "unchanged"
    assert _output()[: len(original_file.read_bytes())] == original_file.read_bytes()


def test_code_refs_hold_their_vanilla_values() -> None:
    for site in IP_EFFECT_CODE_REFS:
        write_file.seek(site.at)
        assert write_file.read(site.encoding.width) == site.value(IP_EFFECT_TABLE)


def test_an_edit_repacks_when_another_effect_shrinks() -> None:
    replace_entry(IPEffect.from_index(0).code, "effect", block(sequence(end())))
    grown = IPEffect.from_index(24)
    grown.code.body[-1:-1] = sequence(physical_attack(), physical_attack())
    grown.write()
    reread = IPEffect.reread(24)
    assert "L_001E" in _labels(reread.code)
    assert reread.build()[: len(grown.build())] == grown.build()


@pytest.mark.parametrize("index", [24, 25, 26])
def test_ip_effects_24_to_26_keep_their_jump_after_a_move(monkeypatch: pytest.MonkeyPatch, index: int) -> None:
    monkeypatch.setattr(ip_effect, "IP_EFFECTS_MOVABLE", True)
    effect = IPEffect.from_index(index)
    effect.code.body[-1:-1] = sequence(*[physical_attack()] * 20)
    effect.write()
    assert ip_effect_table().address != IP_EFFECT_TABLE
    reread = IPEffect.reread(index)
    assert "L_001E" in _labels(reread.code)
    assert reread.build()[: len(effect.build())] == effect.build()


def test_growth_needs_the_table_move_until_its_code_refs_are_verified() -> None:
    effect = IPEffect.from_index(24)
    effect.code.body[-1:-1] = sequence(*[physical_attack()] * 20)
    pool()  # the first use expands the ROM; take the snapshot after that
    before = _output()
    with pytest.raises(TableNotMovable):
        effect.write()
    assert _output() == before


def test_ips_sharing_an_effect_share_one_object() -> None:
    mirrors = [ip for ip in (IPAttack.from_pointer(p) for p in IPAttackObject.pointers) if ip.effect == 0x5C]  # noqa: PLR2004
    assert len(mirrors) >= 2  # noqa: PLR2004
    assert IPEffect.from_index(mirrors[0].effect) is IPEffect.from_index(mirrors[1].effect)


def test_appending_an_effect_gives_a_valid_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ip_effect, "IP_EFFECTS_MOVABLE", True)
    index = append_ip_effect(sequence(physical_attack()))
    assert index == IP_EFFECT_COUNT
    ip = IPAttack.from_pointer(IPAttackObject.pointers[0])
    ip.effect = index
    ip.write()
    ip_effect_table().write()
    reread = IPEffect.reread(index)
    expected = assemble(Script(L2BASM, [Data(b"\xff"), Label("effect"), *block(sequence(physical_attack()))]), 0).data
    assert reread.build()[: len(expected)] == expected  # the last record of a moved table reads up to the bank end
    write_file.seek(IPAttackObject.pointers[0])  # IPAttack reads the original ROM (HER-179): check the output bytes
    assert int.from_bytes(write_file.read(IPAttackObject.effect), "little") == index


@pytest.mark.parametrize("base", [Patch.FRUE, Patch.SPEKKIO, Patch.KUREJI])
def test_unchanged_ip_effects_write_nothing_on_each_base_patch(base: Patch) -> None:
    apply_patch(base)
    before = _output()
    assert ip_effect_table().write() == "unchanged"
    assert _output() == before
