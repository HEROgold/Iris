"""``CapsuleAttackNames``: the capsule attack-name table (SP list text) read from, and written to, the output."""

from collections.abc import Iterator

import pytest

from enums.patches import Patch
from helpers.files import original_file, write_file
from patcher import apply_patch
from structures.capsule_attack_names import CapsuleAttackNames
from tests.reset_file import reset_file


TABLE = 0x12DF00
BANK_END = 0x130000
VANILLA_COUNT = 78


@pytest.fixture(autouse=True)
def _clean_output() -> Iterator[None]:
    reset_file()
    yield
    reset_file()


def _output() -> bytes:
    write_file.flush()
    write_file.seek(0)
    return write_file.read()


def _names_in(rom: bytes) -> list[bytes]:
    """Independent reader: u16 offsets relative to the table, null-terminated strings."""
    first = int.from_bytes(rom[TABLE:TABLE + 2], "little")
    count = first // 2
    offsets = [int.from_bytes(rom[TABLE + 2 * i:TABLE + 2 * i + 2], "little") for i in range(count)]
    for offset in offsets:
        assert TABLE + offset < BANK_END
    return [rom[TABLE + o:rom.index(b"\x00", TABLE + o)] for o in offsets]


def test_reads_the_vanilla_names() -> None:
    names = CapsuleAttackNames()
    assert len(names) == VANILLA_COUNT
    assert names[0] == "Nothing"
    assert names[1] == "Foomy punch"
    assert names[VANILLA_COUNT - 1] == "Inferno"


def test_loading_is_lazy() -> None:
    names = CapsuleAttackNames()
    apply_patch(Patch.FRUE)  # a base patch applied after construction but before first use
    assert names[1] == _names_in(_output())[1].decode()


def test_unload_rereads_on_next_use() -> None:
    names = CapsuleAttackNames()
    names.add("Firebird")
    names.unload()
    assert len(names) == VANILLA_COUNT
    assert not names.dirty


def test_unchanged_table_is_not_written() -> None:
    before = _output()
    names = CapsuleAttackNames()
    names.write()
    assert _output() == before
    assert not names.dirty


def test_added_name_is_readable_after_write() -> None:
    before = _output()
    names = CapsuleAttackNames()
    index = names.add("Firebird")
    assert index == VANILLA_COUNT
    assert names.dirty
    names.write()
    assert not names.dirty
    after = _output()
    assert _names_in(after) == [*_names_in(before), b"Firebird"]
    assert CapsuleAttackNames()[index] == "Firebird"


def test_many_new_names_spill_into_free_space_in_the_bank() -> None:
    before = _output()
    names = CapsuleAttackNames()
    added = [f"New attack {i:02}" for i in range(6)]
    for name in added:
        names.add(name)
    names.write()
    after = _output()
    assert _names_in(after) == [*_names_in(before), *(n.encode() for n in added)]
    changed = [i for i in range(len(before)) if before[i] != after[i]]
    footprint_end = TABLE + 2 * VANILLA_COUNT + sum(len(n) + 1 for n in _names_in(before))
    outside = [i for i in changed if not TABLE <= i < footprint_end]
    assert outside, "expected the overflow to land outside the table's own footprint"
    assert all(before[i] == 0 for i in outside), "overflow may only use bytes that were zero"
    assert all(i < BANK_END for i in outside)


def test_rewriting_after_a_spill_frees_the_old_overflow() -> None:
    names = CapsuleAttackNames()
    for i in range(6):
        names.add(f"New attack {i:02}")
    names.write()
    reread = CapsuleAttackNames()
    reread.add("One more")
    reread.write()
    assert _names_in(_output())[-1] == b"One more"
    assert len(_names_in(_output())) == VANILLA_COUNT + 7


def test_names_come_from_the_output_so_base_patches_are_kept() -> None:
    apply_patch(Patch.FRUE)
    frue = _names_in(_output())
    assert frue != _names_in(original_file.read_bytes())
    names = CapsuleAttackNames()
    names.add("Firebird")
    names.write()
    assert _names_in(_output()) == [*frue, b"Firebird"]


@pytest.mark.parametrize("bad", ["", "Fire\x00bird", "Fénix"])
def test_rejects_names_the_table_cannot_hold(bad: str) -> None:
    with pytest.raises(ValueError, match="name"):
        CapsuleAttackNames().add(bad)
