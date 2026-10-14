"""Ancient Cave blue chests as count-based checks (Iris-Dev#21): an Archipelago build hooks the chest routine at
$8E:C1EB, reads the blue-chest config bytes (0/0, off, by default), and saves, loads and clears the SRAM counter with
the save slot and the new game; a plain build keeps the vanilla chest routine. What the hook does at run time is checked
in Mesen (tests/emulator/blue_chests.lua)."""

from collections.abc import Iterator

import pytest
from iris.build import Options, build
from iris.constants import (
    AP_OPT_BLUE_CHEST_COUNT,
    AP_OPT_BLUE_CHESTS_ENABLED,
    AP_SRAM_BLUE_CHESTS,
    AP_SRAM_BLUE_CHESTS_SAVED,
    BLUE_CHESTS_CODE_REGION,
    NEW_GAME_CODE_REGION,
)
from iris.enums.patches import Patch
from iris.helpers.addresses import address_from_lorom, address_to_lorom
from iris.helpers.files import original_file, session, use
from iris.structures.monster import Monster
from iris.structures.shop import Shop
from iris.tables import select, selected


HOOK_SITE = 0x0741EB
"""$8E:C1EB, the chest animation in the chest routine."""
VANILLA = bytes.fromhex("22 59 F5 83")
"""JSL $83F559."""
SAVE_SITE = 0x016B61
"""$82:EB61: rx.asm's SaveRX hook."""
LOAD_SITE = 0x016AD5
"""$82:EAD5: rx.asm's LoadRX hook."""


def _long(opcode: int, address: int) -> bytes:
    return bytes([opcode]) + address.to_bytes(3, "little")


@pytest.fixture(autouse=True)
def _restore_session() -> Iterator[None]:
    """build() swaps the session; give the rest of the suite back the one conftest opened."""
    rom, patch = session(), selected()
    verify_pointers, easy_mode = Shop.verify_pointers, Monster.easy_mode
    yield
    Shop.verify_pointers, Monster.easy_mode = verify_pointers, easy_mode
    select(patch)
    use(rom)


@pytest.fixture(scope="module")
def source() -> bytes:
    return original_file.read_bytes()


@pytest.fixture(scope="module", params=[False, True], ids=["linear", "open_world"])
def ap_rom(request: pytest.FixtureRequest, source: bytes) -> Iterator[bytes]:
    """Built once per base patch; module fixtures run before _restore_session, so this one restores its own."""
    rom, patch = session(), selected()
    verify_pointers, easy_mode = Shop.verify_pointers, Monster.easy_mode
    yield build(source, Options(1, selected_patch=Patch.VANILLA, archipelago=True, open_world=request.param))
    Shop.verify_pointers, Monster.easy_mode = verify_pointers, easy_mode
    select(patch)
    use(rom)


def _jsl_target(rom: bytes, site: int) -> int:
    assert rom[site] == 0x22
    return address_from_lorom(int.from_bytes(rom[site + 1:site + 4], "little"))


def test_vanilla_site(source: bytes) -> None:
    assert source[HOOK_SITE:HOOK_SITE + 4] == VANILLA
    assert source[HOOK_SITE + 4:HOOK_SITE + 7] == bytes.fromhex("A2 00 80")  # $8E:C1EF LDX #$8000, the item get


def test_archipelago_hooks_the_chest_routine_and_reads_the_config(ap_rom: bytes) -> None:
    assert ap_rom[HOOK_SITE:HOOK_SITE + 4] == _long(0x5C, address_to_lorom(BLUE_CHESTS_CODE_REGION.start))
    code = ap_rom[BLUE_CHESTS_CODE_REGION.start:BLUE_CHESTS_CODE_REGION.stop]
    assert code.startswith(VANILLA + bytes.fromhex("08 C2 20") + _long(0xAF, 0x7FD4EF) + bytes.fromhex("29 00 40"))
    assert _long(0xAF, address_to_lorom(AP_OPT_BLUE_CHESTS_ENABLED)) in code
    assert _long(0xAF, AP_SRAM_BLUE_CHESTS) + _long(0xCF, address_to_lorom(AP_OPT_BLUE_CHEST_COUNT)) in code
    assert _long(0x8F, AP_SRAM_BLUE_CHESTS) in code
    assert _long(0x5C, 0x8EC2DC) in code  # skip the item get
    assert _long(0x5C, 0x8EC1EF) in code  # the item get


def test_default_is_off(ap_rom: bytes) -> None:
    assert ap_rom[AP_OPT_BLUE_CHESTS_ENABLED:AP_OPT_BLUE_CHEST_COUNT + 2] == bytes(3)


def test_save_and_load_keep_the_counter_per_slot(ap_rom: bytes) -> None:
    save = ap_rom[_jsl_target(ap_rom, SAVE_SITE):][:32]
    # JSL $8090C9 : SEP #$10 : REP #$20 : ASL : TAX : LDA counter : STA saved,X
    assert save.startswith(
        _long(0x22, 0x8090C9) + bytes.fromhex("E2 10 C2 20 0A AA")
        + _long(0xAF, AP_SRAM_BLUE_CHESTS) + _long(0x9F, AP_SRAM_BLUE_CHESTS_SAVED),
    )
    load = ap_rom[_jsl_target(ap_rom, LOAD_SITE):][:40]
    # ... LDA saved,X : CMP count : BCC + : BEQ + : LDA #0 : +: STA counter
    assert load.startswith(
        _long(0x22, 0x809099) + bytes.fromhex("E2 10 C2 20 0A AA")
        + _long(0xBF, AP_SRAM_BLUE_CHESTS_SAVED) + _long(0xCF, address_to_lorom(AP_OPT_BLUE_CHEST_COUNT))
        + bytes.fromhex("90 05 F0 03 A9 00 00") + _long(0x8F, AP_SRAM_BLUE_CHESTS),
    )


def test_new_game_clears_the_counter(ap_rom: bytes) -> None:
    code = ap_rom[NEW_GAME_CODE_REGION.start:NEW_GAME_CODE_REGION.stop]
    assert _long(0x8F, 0xF02802) + _long(0x8F, AP_SRAM_BLUE_CHESTS) in code


def test_plain_build_keeps_the_vanilla_chest_routine(source: bytes) -> None:
    rom = build(source, Options(1, selected_patch=Patch.VANILLA))
    assert rom[HOOK_SITE:HOOK_SITE + 4] == VANILLA
    assert _long(0x8F, AP_SRAM_BLUE_CHESTS) not in rom[NEW_GAME_CODE_REGION.start:NEW_GAME_CODE_REGION.stop]
