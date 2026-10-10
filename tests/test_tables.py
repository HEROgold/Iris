"""Importing Iris doesn't read the command line; the table set is picked at run time (Iris-Dev#4)."""

from collections.abc import Iterator

import pytest

from iris import args
from iris.args import parse_args
from iris.enums.patches import Patch
from iris.tables import BlueChestObject, CapAttackNameObject, ZoneObject, frue, kureji, select, selected, vanilla


@pytest.fixture
def restore_tables() -> Iterator[None]:
    before = selected()
    yield
    select(before)


def test_importing_args_parses_nothing() -> None:
    assert not hasattr(args, "args")


def test_parse_args_picks_the_patch() -> None:
    assert parse_args(["--file", "rom.smc"]).selected_patch is Patch.FRUE
    assert parse_args(["--file", "rom.smc", "--vanilla"]).selected_patch is Patch.VANILLA
    assert parse_args(["--file", "rom.smc", "--kureji"]).selected_patch is Patch.KUREJI


def test_parse_args_rejects_unimplemented_flags() -> None:
    with pytest.raises(AssertionError):
        parse_args(["--file", "rom.smc", "--equip-everyone"])


@pytest.mark.usefixtures("restore_tables")
def test_select_switches_the_tables() -> None:
    select(Patch.VANILLA)
    assert BlueChestObject.address == vanilla.BlueChestObject.address
    select(Patch.KUREJI)
    assert selected() is Patch.KUREJI
    assert BlueChestObject.address == kureji.BlueChestObject.address != vanilla.BlueChestObject.address


@pytest.mark.usefixtures("restore_tables")
def test_missing_tables_fall_back_to_the_patch_below() -> None:
    select(Patch.KUREJI)
    assert CapAttackNameObject.address == vanilla.CapAttackNameObject.address  # only vanilla lists it
    assert ZoneObject.address == vanilla.ZoneObject.address
    select(Patch.SPEKKIO)
    assert not hasattr(frue, "ZoneObject")
    assert ZoneObject.address == vanilla.ZoneObject.address
