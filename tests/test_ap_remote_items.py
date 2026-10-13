"""Chests and grants holding the AP item say who it's for and give nothing, but still count as checked (Iris-Dev#19).

Static checks on the committed base patches (``tools/build_ap_basepatch.py --check`` keeps them current): the hooks of
``remote_items.asm``, the paths their AP-item branches take, and the remote-text table the world fills.
"""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
from iris.constants import (
    AP_REMOTE_CHEST_TEXT_COUNT,
    AP_REMOTE_CHEST_TEXT_ENTRY_SIZE,
    AP_REMOTE_CHEST_TEXT_OFFSET,
    AP_REMOTE_TEXT_SIZE,
    REMOTE_ITEMS_CODE_REGION,
)
from iris.helpers import files
from iris.helpers.addresses import address_from_lorom, address_to_lorom
from iris.patches.archipelago.overworld.ap_item import AP_ITEM_INDEX


bsdiff4 = pytest.importorskip("bsdiff4")

from tools.build_ap_basepatch import PATCHES, vanilla_image


WORLD_GRANT_TEXT = Path(__file__).resolve().parents[2] / "lufia2ow" / "grant_text.py"
JSL, JML, RTS = 0x22, 0x5C, 0x60
CHEST_TEXT_HOOK = 0x8EC225
"""Vanilla ``JSL $8EB5FB``: "Found " + the item's name into $7E:E000."""
CHEST_GIVE_HOOK = 0x8EC2CA
"""Vanilla ``REP #$10 : LDA $7FD4EF``: the item-get menu follows."""
GRANT_GIVE_HOOK = 0x80A435
"""Vanilla ``STA $7FD4F1`` in the 20/21 opcodes' item get."""
CHEST_SKIP = 0x8EC2DC
"""``STZ $09CF : STZ $09D0``, then the routine's end."""
OPENED_BIT = 0x8EC199
"""The caller: if $09CF/$09D0 came back zero, set the chest's opened bit (``ORA/STA $093B,x``)."""
GRANT_END = 0x80A47F
"""``RTS`` back to the opcode, which carries on with the script (its flags, its text)."""


def _world_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("grant_text", WORLD_GRANT_TEXT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def roms() -> list[tuple[bytes, bytes]]:
    """(vanilla, base ROM) for the linear and the open-world base patch."""
    vanilla = vanilla_image(files.original_file)
    return [(vanilla, bsdiff4.patch(vanilla, patch_file.read_bytes())) for patch_file, _ in PATCHES]


def _at(rom: bytes, snes: int, size: int) -> bytes:
    offset = address_from_lorom(snes)
    return rom[offset : offset + size]


def _target(rom: bytes, snes: int, opcode: int) -> int:
    code = _at(rom, snes, 4)
    assert code[0] == opcode, f"${snes:06X}: {code.hex()}"
    return int.from_bytes(code[1:], "little")


def _in_region(snes: int) -> bool:
    return address_from_lorom(snes) in REMOTE_ITEMS_CODE_REGION


def _code(rom: bytes) -> bytes:
    return rom[REMOTE_ITEMS_CODE_REGION.start : REMOTE_ITEMS_CODE_REGION.stop]


def _long(snes: int) -> bytes:
    return snes.to_bytes(3, "little")


def test_hooks_jump_into_the_remote_items_code(roms: list[tuple[bytes, bytes]]) -> None:
    for _, rom in roms:
        assert _in_region(_target(rom, CHEST_TEXT_HOOK, JSL))
        assert _in_region(_target(rom, CHEST_GIVE_HOOK, JML))
        assert _in_region(_target(rom, GRANT_GIVE_HOOK, JML))


def test_chest_text_starts_with_the_vanilla_text(roms: list[tuple[bytes, bytes]]) -> None:
    for vanilla, rom in roms:
        start = _target(rom, CHEST_TEXT_HOOK, JSL)
        assert _at(rom, start, 4) == _at(vanilla, CHEST_TEXT_HOOK, 4)  # the overwritten JSL $8EB5FB runs first


def test_ap_item_skips_the_item_get_but_the_chest_is_still_opened(roms: list[tuple[bytes, bytes]]) -> None:
    """The chest's AP-item branch jumps to $8E:C2DC, which zeroes $09CF/$09D0; back in the caller, zero means "set the
    opened bit". Both stretches are vanilla."""
    ap_item = AP_ITEM_INDEX.to_bytes(2, "little")
    for vanilla, rom in roms:
        code = _code(rom)
        assert bytes([0x29, 0xFF, 0x81, 0xC9]) + ap_item in code  # AND #$81FF : CMP #$01CA
        assert bytes([JML]) + _long(CHEST_SKIP) in code
        assert bytes([JML]) + _long(CHEST_GIVE_HOOK + 6) in code  # every other item: back after the overwritten code
        assert _at(rom, CHEST_SKIP, 6) == bytes.fromhex("9CCF099CD009")
        assert _at(rom, CHEST_SKIP, 0x20) == _at(vanilla, CHEST_SKIP, 0x20)
        assert _at(rom, OPENED_BIT, 0x14) == _at(vanilla, OPENED_BIT, 0x14)
        assert _at(rom, OPENED_BIT + 0xE, 6) == bytes.fromhex("1D3B099D3B09")  # ORA $093B,x : STA $093B,x


def test_ap_item_grant_skips_only_the_item_get(roms: list[tuple[bytes, bytes]]) -> None:
    """The grant's AP-item branch returns from the item get ($80:A47F, RTS); the opcode then carries on with the script,
    so the grant's flag and text still run."""
    ap_item = AP_ITEM_INDEX.to_bytes(2, "little")
    for vanilla, rom in roms:
        code = _code(rom)
        assert bytes([0xC9]) + ap_item in code
        assert bytes([JML]) + _long(GRANT_END) in code
        assert bytes([JML]) + _long(GRANT_GIVE_HOOK + 4) in code
        assert _at(rom, GRANT_END, 1) == bytes([RTS])
        assert _at(rom, 0x80A414, 0x17) == _at(vanilla, 0x80A414, 0x17)  # the 20/21 opcodes: JSR $A42B, BRL $9D00


def test_chest_text_reads_the_config_table(roms: list[tuple[bytes, bytes]]) -> None:
    table = _long(address_to_lorom(AP_REMOTE_CHEST_TEXT_OFFSET))
    size = AP_REMOTE_CHEST_TEXT_COUNT * AP_REMOTE_CHEST_TEXT_ENTRY_SIZE
    for _, rom in roms:
        assert _code(rom).count(bytes([0xBF]) + table) == 2  # LDA table,x: the empty test, then the copy
        assert rom[AP_REMOTE_CHEST_TEXT_OFFSET : AP_REMOTE_CHEST_TEXT_OFFSET + size] == bytes(size)  # filled per seed


def test_remote_text() -> None:
    world = _world_module()
    assert world.REMOTE_SIZE == AP_REMOTE_TEXT_SIZE
    assert world.remote_text("Potion", "Bob") == b"Found Potion for Bob."
    assert world.remote_text("Potion", "Tester2") == b"Found Potion\x03for Tester2."  # 25 characters
    assert world.remote_text("Progressive Sword", "Tester2") == b"Found Progressive Sword\x03for Tester2."
    assert world.remote_text("Master Sword of the Ages", "Tester2") == b"Found Master Sword of\x03for Tester2."
    assert world.remote_text("Supercalifragilisticexpialidocious", "Ünïcode Player") == (
        b"Found Supercalifragilist\x03for n code Player."
    )
    longest = world.remote_text("x" * 40, "y" * 40)
    assert len(longest) == AP_REMOTE_TEXT_SIZE
    assert all(len(line) <= world.LINE_WIDTH for line in longest.split(b"\x03"))
    entry = world.remote_chest_entry("x" * 40, "y" * 40, AP_REMOTE_CHEST_TEXT_ENTRY_SIZE)
    assert len(entry) == AP_REMOTE_CHEST_TEXT_ENTRY_SIZE
    assert entry[AP_REMOTE_TEXT_SIZE:] == bytes(AP_REMOTE_CHEST_TEXT_ENTRY_SIZE - AP_REMOTE_TEXT_SIZE)
