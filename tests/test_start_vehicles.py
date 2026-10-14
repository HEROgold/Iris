"""Start with the Mermaid jade and/or the Engine (Iris-Dev#16, #24): the new-game state each option builds.

``tests/emulator/start_vehicles.lua`` checks the same state in Mesen; this checks the bytes the build lays down.
"""

from collections.abc import Iterator

import pytest
from iris.build import Options, build
from iris.constants import AP_OPT_START_ENGINE, AP_OPT_START_MERMAID_JADE
from iris.enums.patches import Patch
from iris.helpers import files
from iris.helpers.addresses import address_from_lorom, address_to_lorom
from iris.helpers.files import session, use
from iris.structures.monster import Monster
from iris.structures.shop import Shop
from iris.tables import select, selected


HANDOFF = 0x1ADC2
"""$03:ADC2, the new-game hook's JML."""
SHIP_TYPE_OPCODE = 0x3D6F
"""$80:BD6F, event opcode 7C's ``STA $09DF : BRL $9D00``."""
WARP_GATE_BRANCH = 0x31C31
"""$86:9C31, Warp arrival's ``BNE $9C6F`` on the Auralio water gate (flag 149)."""
VANILLA_SHIP_TYPE_OPCODE = bytes.fromhex("8D DF 09 82 8B DF")
ELCID_DOCK = 0xC8
JML, BRA, BNE = 0x5C, 0x80, 0xD0


def _ship_state(scenario_bits: int, ship_type: int) -> bytes:
    """The hook's stores: the item bits in $0920, $09E0 = 0, $09EE = Elcid's dock, $09DF = the ship type."""
    return bytes.fromhex(
        f"AF 20 09 7E 09 {scenario_bits:02X} 8F 20 09 7E A9 00 8F E0 09 7E A9 {ELCID_DOCK:02X} 8F EE 09 7E "
        f"A9 {ship_type:02X} 8F DF 09 7E",
    )


def _lda_long(offset: int) -> bytes:
    return bytes([0xAF]) + address_to_lorom(offset).to_bytes(3, "little")


@pytest.fixture(autouse=True)
def _restore_session() -> Iterator[None]:
    """Give the rest of the suite back the session conftest opened."""
    rom, patch = session(), selected()
    verify_pointers, easy_mode = Shop.verify_pointers, Monster.easy_mode
    yield
    Shop.verify_pointers, Monster.easy_mode = verify_pointers, easy_mode
    select(patch)
    use(rom)


@pytest.fixture(scope="module")
def source() -> bytes:
    return files.original_file.read_bytes()


def _hook(rom: bytes) -> bytes:
    assert rom[HANDOFF] == JML
    start = address_from_lorom(int.from_bytes(rom[HANDOFF + 1 : HANDOFF + 4], "little"))
    return rom[start : start + 0x200]


@pytest.mark.parametrize(
    ("jade", "engine", "bits", "ship_type"),
    [(True, False, 0x10, 1), (False, True, 0x20, 2), (True, True, 0x30, 2)],
    ids=["jade", "engine", "both"],
)
def test_standalone_start_places_the_vehicle_at_elcid(
    source: bytes,
    jade: bool,
    engine: bool,
    bits: int,
    ship_type: int,  # noqa: FBT001 - parametrized
) -> None:
    rom = build(source, Options(1, selected_patch=Patch.VANILLA, start_mermaid_jade=jade, start_engine=engine))
    assert _ship_state(bits, ship_type) in _hook(rom)
    # Event opcode 7C never lowers the ship type, and Warp takes the ship along before the water gate opens.
    assert rom[SHIP_TYPE_OPCODE] == JML
    assert rom[SHIP_TYPE_OPCODE + 4 : SHIP_TYPE_OPCODE + 6] == b"\xea\xea"
    ship_upgrade = address_from_lorom(int.from_bytes(rom[SHIP_TYPE_OPCODE + 1 : SHIP_TYPE_OPCODE + 4], "little"))
    assert rom[ship_upgrade : ship_upgrade + 14] == bytes.fromhex("CF DF 09 7E 90 04 8F DF 09 7E 5C 00 9D 80")
    assert rom[WARP_GATE_BRANCH] == BRA


def test_without_the_options_nothing_changes(source: bytes) -> None:
    rom = build(source, Options(1, selected_patch=Patch.VANILLA))
    assert rom[SHIP_TYPE_OPCODE : SHIP_TYPE_OPCODE + 6] == VANILLA_SHIP_TYPE_OPCODE
    assert rom[WARP_GATE_BRANCH] == BNE
    hook = _hook(rom)
    assert bytes.fromhex("8F DF 09 7E") not in hook
    assert _lda_long(AP_OPT_START_MERMAID_JADE) not in hook


def test_archipelago_reads_the_start_bytes_and_sets_the_item_bits(source: bytes) -> None:
    rom = build(source, Options(1, selected_patch=Patch.VANILLA, archipelago=True))
    hook = _hook(rom)
    jade = hook.index(_lda_long(AP_OPT_START_MERMAID_JADE))
    engine = hook.index(_lda_long(AP_OPT_START_ENGINE))
    # Mermaid Jade: Ship + Submarine ($0921 bits $04|$08). Engine: Ship ($0921 bit $04) + Engine ($0920 bit $20).
    assert bytes.fromhex("AF 21 09 7E 09 0C 8F 21 09 7E") in hook[jade:engine]
    after = hook[engine:]
    assert bytes.fromhex("AF 21 09 7E 09 04 8F 21 09 7E AF 20 09 7E 09 20 8F 20 09 7E") in after
    # key_items.asm builds and places the ship: the standalone hooks stay out.
    assert rom[SHIP_TYPE_OPCODE : SHIP_TYPE_OPCODE + 6] == VANILLA_SHIP_TYPE_OPCODE
    assert bytes.fromhex("8F DF 09 7E") not in hook
    assert rom[AP_OPT_START_MERMAID_JADE] == rom[AP_OPT_START_ENGINE] == 0  # the apworld writes them per seed
