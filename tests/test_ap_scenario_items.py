"""The scenario-item removal mode (Iris-Dev#26): an Archipelago build hooks the story's "Remove item" worker at
$82:FA87 and reads the mode byte from the config block, defaulting to vanilla removals; a plain build keeps the vanilla
instruction. What the hook does at run time is checked in Mesen (tests/emulator)."""

from collections.abc import Iterator

import pytest
from iris.build import Options, build
from iris.constants import AP_OPT_SCENARIO_ITEM_MODE, SCENARIO_ITEMS_CODE_REGION
from iris.enums.patches import Patch
from iris.helpers.addresses import address_to_lorom
from iris.helpers.files import original_file, session, use
from iris.structures.monster import Monster
from iris.structures.shop import Shop
from iris.tables import select, selected


HOOK_SITE = 0x017A87
"""$82:FA87, in the remove worker $82:FA77."""
VANILLA = bytes.fromhex("BF C3 D8 8E")
"""LDA $8ED8C3,X: the held bit's mask."""
REMOVE_TAIL = bytes.fromhex("59 1E 09 99 1E 09 A9 00 00 18 60")
"""EOR $091E,Y : STA $091E,Y : LDA #$0000 : CLC : RTS, left as it is."""


def _jsl(offset: int) -> bytes:
    return bytes([0x22]) + address_to_lorom(offset).to_bytes(3, "little")


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


def test_vanilla_site(source: bytes) -> None:
    assert source[HOOK_SITE:HOOK_SITE + 4] == VANILLA
    assert source[HOOK_SITE + 4:HOOK_SITE + 15] == REMOVE_TAIL


def test_archipelago_hooks_the_worker_and_reads_the_mode(ap_rom: bytes) -> None:
    assert ap_rom[HOOK_SITE:HOOK_SITE + 4] == _jsl(SCENARIO_ITEMS_CODE_REGION.start)
    assert ap_rom[HOOK_SITE + 4:HOOK_SITE + 15] == REMOVE_TAIL
    code = ap_rom[SCENARIO_ITEMS_CODE_REGION.start:SCENARIO_ITEMS_CODE_REGION.stop]
    # LDA.l mode : AND #$00FF : BNE .keep : LDA.l $8ED8C3,X : RTL : .keep: LDA #$0000 : RTL
    mode = bytes([0xAF]) + address_to_lorom(AP_OPT_SCENARIO_ITEM_MODE).to_bytes(3, "little")
    assert code.startswith(mode + bytes.fromhex("29 FF 00 D0 05") + VANILLA + bytes.fromhex("6B A9 00 00 6B"))


def test_default_is_vanilla_removals(ap_rom: bytes) -> None:
    assert ap_rom[AP_OPT_SCENARIO_ITEM_MODE] == 0


def test_plain_build_keeps_the_vanilla_worker(source: bytes) -> None:
    rom = build(source, Options(1, selected_patch=Patch.VANILLA))
    assert rom[HOOK_SITE:HOOK_SITE + 4] == VANILLA
