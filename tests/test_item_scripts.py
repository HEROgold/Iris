"""Item records on rom_space.Table: unchanged output, header edits, script edits, flag bits and property words."""

from collections.abc import Iterator
from copy import deepcopy

import pytest

from enums.flags import ItemEffects
from enums.patches import Patch
from helpers.files import original_file, write_file
from patcher import apply_patch
from rom_space.pool import reset_pool
from scripting.core import Label, assemble
from scripting.l2basm.helpers import physical_attack, sequence
from scripting.l2basm.records import ITEM_WORDS
from structures import subroutine
from structures.item import Item, item_table, reset_item_table
from tables import ItemObject
from tests.reset_file import reset_file


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    reset_file()
    reset_pool()
    subroutine.reset()
    reset_item_table()
    yield
    reset_file()
    reset_pool()
    subroutine.reset()
    reset_item_table()


def _output() -> bytes:
    write_file.flush()
    write_file.seek(0)
    return write_file.read()


def _diff_offsets(a: bytes, b: bytes) -> list[int]:
    return [i for i, (x, y) in enumerate(zip(a, b, strict=False)) if x != y]


def _words(record: bytes) -> list[int]:
    flags = int.from_bytes(record[9:11], "little")
    return [int.from_bytes(record[ITEM_WORDS + 2 * i : ITEM_WORDS + 2 * i + 2], "little") for i in range(flags.bit_count())]


def test_every_item_builds_its_vanilla_record() -> None:
    table = item_table()
    rom = original_file.read_bytes()
    assert len(table.records) == ItemObject.count
    for record, start in zip(table.records, table.starts(), strict=True):
        data = record.build()  # type: ignore[attr-defined]
        assert rom[start : start + len(data)] == data, record


def test_item_effects_bit_0_is_the_menu_script() -> None:
    menu_items = [Item.from_index(i) for i in range(ItemObject.count) if "menu" in Item.from_index(i).entries()]
    assert len(menu_items) == 27  # noqa: PLR2004
    assert all(ItemEffects.MENU_EFFECT in item.item_effects for item in menu_items)


def test_unchanged_items_write_nothing() -> None:
    for i in range(ItemObject.count):
        Item.from_index(i).write()
    assert _output()[: len(original_file.read_bytes())] == original_file.read_bytes()


def test_header_edit_writes_only_the_header() -> None:
    potion = Item.from_index(0)
    potion.price += 1
    potion.write()
    start = item_table().starts()[0]
    assert set(_diff_offsets(original_file.read_bytes(), _output())) <= set(range(start, start + ITEM_WORDS))


def test_writing_a_copy_writes_the_copy() -> None:
    copy = deepcopy(Item.from_index(3))
    copy.price = 1234
    copy.write()
    reset_item_table()
    assert Item.from_index(3).price == 1234  # noqa: PLR2004


def test_growing_a_weapon_script_keeps_every_word(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subroutine, "SUBROUTINES_MOVABLE", True)
    index = next(i for i in range(ItemObject.count) if "weapon" in Item.from_index(i).entries())
    item = Item.from_index(index)
    before = _words(item.build())
    names = item.entries()
    item.replace_script("weapon", sequence(*[physical_attack()] * 30))
    item.write()
    reread = Item.reread(index)
    assert reread.build()[: len(item.build())] == item.build()
    after = _words(reread.build())
    assert len(after) == len(before)
    out = assemble(reread.code, reread.script_origin())  # type: ignore[arg-type]
    for name in names:
        assert reread.script_word(name) == reread.script_origin() + out.labels[name]
    for bit, value in reread.properties.items():
        assert after[(int(reread.flags()) & ((1 << bit) - 1)).bit_count()] == value


def test_adding_a_battle_effect_sets_bit_1_and_places_the_word(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subroutine, "SUBROUTINES_MOVABLE", True)
    index = next(
        i for i in range(ItemObject.count)
        if "battle" not in Item.from_index(i).entries() and Item.from_index(i).properties
    )
    item = Item.from_index(index)
    properties = dict(item.properties)
    item.replace_script("battle", sequence(physical_attack()))
    assert ItemEffects.BATTLE_EFFECT in item.item_effects
    item.write()
    reread = Item.reread(index)
    assert "battle" in reread.entries()
    assert reread.properties == properties
    assert reread.build()[: len(item.build())] == item.build()
    labels = {i.name for i in reread.code.body if isinstance(i, Label)}  # type: ignore[union-attr]
    assert "battle" in labels


def test_setting_a_property_bit_adds_its_word_and_clearing_removes_it() -> None:
    item = Item.from_index(0)
    item.item_effects |= ItemEffects.INCREASE_ATP
    assert item.properties[4] == 0
    item.item_effects &= ~ItemEffects.INCREASE_ATP
    assert 4 not in item.properties


def test_script_bits_follow_the_scripts() -> None:
    item = next(Item.from_index(i) for i in range(ItemObject.count) if not Item.from_index(i).entries())
    item.item_effects |= ItemEffects.BATTLE_EFFECT  # no battle script: the bit can't be set from outside
    assert ItemEffects.BATTLE_EFFECT not in item.item_effects


@pytest.mark.parametrize("base", [Patch.FRUE, Patch.SPEKKIO, Patch.KUREJI])
def test_unchanged_items_write_nothing_on_each_base_patch(base: Patch) -> None:
    apply_patch(base)
    before = _output()
    assert item_table().write() == "unchanged"
    assert _output() == before
