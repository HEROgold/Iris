"""$42 subroutine table: round trip through Table, and the move out of bank $96."""

from collections.abc import Iterator

import pytest

from helpers.files import original_file, write_file
from rom_space.pool import bank_of, reset_pool
from scripting.l2basm.records import SUBROUTINE_COUNT, SUBROUTINE_TABLE
from structures import subroutine
from structures.subroutine import SUBROUTINE_CODE_REFS, subroutine_table
from tests.reset_file import reset_file


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    reset_file()
    reset_pool()
    subroutine.reset()
    yield
    reset_file()
    reset_pool()
    subroutine.reset()


def _bodies(table_address: int) -> list[bytes]:
    write_file.flush()
    table = subroutine_table()
    return [record.build() for record in table.records] if table.address == table_address else []


def test_every_subroutine_builds_its_vanilla_bytes() -> None:
    table = subroutine_table()
    rom = original_file.read_bytes()
    starts = table.starts()
    for record, start in zip(table.records, starts, strict=True):
        data = record.build()
        assert rom[start : start + len(data)] == data


def test_unchanged_table_writes_nothing() -> None:
    assert subroutine_table().write() == "unchanged"
    write_file.flush()
    write_file.seek(0)
    assert write_file.read(len(original_file.read_bytes())) == original_file.read_bytes()


def test_code_refs_hold_their_vanilla_values() -> None:
    for site in SUBROUTINE_CODE_REFS:
        write_file.seek(site.at)
        assert write_file.read(site.encoding.width) == site.value(SUBROUTINE_TABLE)


def test_moving_the_table_frees_room_in_bank_96(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subroutine, "SUBROUTINES_MOVABLE", True)
    table = subroutine_table()
    before = [record.build() for record in table.records]
    assert subroutine.make_room_in_bank_96(bank_of(SUBROUTINE_TABLE)) is True
    assert bank_of(table.address) != bank_of(SUBROUTINE_TABLE)
    for site in SUBROUTINE_CODE_REFS:
        write_file.seek(site.at)
        assert write_file.read(site.encoding.width) == site.value(table.address)
    subroutine.reset()
    moved = subroutine_table()
    assert moved.address == table.address
    assert [record.build() for record in moved.records] == before
    assert len(moved.records) == SUBROUTINE_COUNT


def test_make_room_refuses_while_not_movable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subroutine, "SUBROUTINES_MOVABLE", False)
    assert subroutine.make_room_in_bank_96(bank_of(SUBROUTINE_TABLE)) is False


def test_the_table_is_marked_movable() -> None:
    assert subroutine.SUBROUTINES_MOVABLE is True


def test_make_room_ignores_other_banks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subroutine, "SUBROUTINES_MOVABLE", True)
    assert subroutine.make_room_in_bank_96(0x17) is False


def test_moving_the_table_does_not_stretch_the_item_area(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripting.l2basm.records import table_address, table_bound  # noqa: PLC0415

    items = table_address(write_file, "item")
    assert table_bound(write_file, items) == SUBROUTINE_TABLE
    monkeypatch.setattr(subroutine, "SUBROUTINES_MOVABLE", True)
    subroutine.make_room_in_bank_96(bank_of(SUBROUTINE_TABLE))
    write_file.flush()
    assert table_bound(write_file, items) == SUBROUTINE_TABLE
