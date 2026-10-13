"""Iris' own event flags stay clear of every flag a vanilla event script uses (Iris-Dev#14)."""

import re

import pytest

from iris.enums.flags import GOAL_FLAG, SCRATCH_FLAGS_START, VANILLA_UNNAMED_FLAGS, EventFlag
from iris.structures.event_script.dump import dump_all
from tests.reset_file import reset_file


FOUND_FLAGS = [flag for flag in EventFlag if flag.name.startswith("FOUND_")]
GRANT_FLAGS = [EventFlag.RECEIVED_EAR_JEWEL, EventFlag.RECEIVED_DRAGON_EGG_MERIX, EventFlag.RECEIVED_ENGINE]
"""Iris' flags for the grants vanilla left without one (Iris-Dev#22)."""

# 1A/1B set/clear, 15/6A branch on a flag; the 14 chain's flag sub-codes are handled in _vanilla_flags.
_SINGLE = re.compile(r"^\s+[0-9A-F]{4}\. (?:1A|1B|15|6A)\(([0-9A-F]{2})\b", re.MULTILINE)
_CHAIN = re.compile(r"^\s+[0-9A-F]{4}\. 14\(([^)]*)\)", re.MULTILINE)
_FLAG_SUBCODES = {0x00, 0x01, 0x40, 0x41, 0x80, 0x81}
_ITEM_SUBCODES = {0xC0, 0xC2}  # item, quantity
_TWO_OPERAND_SUBCODES = {0x10, 0x12, 0xF0, 0xF8}
_BRANCH_SUBCODES = {0x20, 0x30}  # address


def _chain_flags(operands: list[str]) -> set[int]:
    flags: set[int] = set()
    i = 0
    while i < len(operands) and operands[i] != "FF":
        code = int(operands[i], 16)
        if code in _FLAG_SUBCODES:
            flags.add(int(operands[i + 1], 16))
            i += 2
        elif code in _ITEM_SUBCODES or code in _TWO_OPERAND_SUBCODES:
            i += 3
        elif code in _BRANCH_SUBCODES:
            i += 2
        else:
            msg = f"unknown 0x14 sub-code {code:#04x} in {operands}"
            raise AssertionError(msg)
    return flags


@pytest.fixture(scope="module")
def vanilla_flags() -> set[int]:
    reset_file()
    dump = dump_all()
    flags = {int(flag, 16) for flag in _SINGLE.findall(dump)}
    for chain in _CHAIN.findall(dump):
        flags |= _chain_flags(chain.split("-"))
    return flags


def test_found_flags_are_unused_by_vanilla(vanilla_flags: set[int]) -> None:
    assert len(FOUND_FLAGS) == 7
    assert not {int(flag) for flag in FOUND_FLAGS} & vanilla_flags


def test_grant_flags_are_unused_by_vanilla(vanilla_flags: set[int]) -> None:
    assert not {int(flag) for flag in GRANT_FLAGS} & vanilla_flags
    assert all(flag < SCRATCH_FLAGS_START for flag in GRANT_FLAGS)


def test_free_flags_are_unused_by_vanilla(vanilla_flags: set[int]) -> None:
    assert not set(EventFlag.free_flags()) & vanilla_flags


def test_every_vanilla_flag_is_named_or_listed(vanilla_flags: set[int]) -> None:
    named = {int(flag) for flag in EventFlag}
    below_scratch = {flag for flag in vanilla_flags if flag < SCRATCH_FLAGS_START}
    assert below_scratch <= named | VANILLA_UNNAMED_FLAGS


def test_found_flags_are_below_the_scratch_flags() -> None:
    assert all(flag < SCRATCH_FLAGS_START for flag in FOUND_FLAGS)
    assert not set(EventFlag.free_flags()) & set(range(SCRATCH_FLAGS_START, 256))


def test_goal_is_daos_defeated() -> None:
    assert GOAL_FLAG == EventFlag.DAOS_DEFEATED == 115
