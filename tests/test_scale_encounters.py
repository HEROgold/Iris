"""Tests for --scale-encounters: the baked level->formation table and the asar half of the patch.

The runtime behaviour (does a fight actually get swapped?) needs an emulator. What is testable here
is that the Python side bakes a well-formed, reproducible table into the reserved region, that the
region is real expansion space, that asar's output leaves the baked data intact, and that the hook
lands on the instruction we expect -- so the site cannot silently drift onto the wrong bytes.
"""

import random
from collections.abc import Iterator

import pytest
from iris.build import Options, build
from iris.constants import (
    AP_OPT_SCALING_ENABLED,
    AP_OPT_SCALING_LOW,
    AP_OPT_SCALING_RANGE,
    SCALE_ENCOUNTERS_CODE,
    SCALE_ENCOUNTERS_LOW,
    SCALE_ENCOUNTERS_RANGE,
    SCALE_ENCOUNTERS_REGION,
    SCALE_ENCOUNTERS_ROM_SIZE,
    SCALE_ENCOUNTERS_TABLE,
    SCALE_ENCOUNTERS_TABLE_SIZE,
)
from iris.enums.patches import Patch
from iris.helpers.addresses import address_to_lorom
from iris.helpers.files import original_file, output_bytes, read_file, session, use, write_file
from iris.patches.HEROgold.scale_encounters import (
    AP_DEFAULT_BAND,
    MAX_LEVEL,
    MIN_LEVEL,
    TIE_TOLERANCE,
    UNUSED_FORMATIONS,
    _build_level_table,
    _candidate_formations,
    _write_scale_data,
    scale_encounters,
)
from iris.structures.formation import EMPTY_SLOT, BattleFormation
from iris.structures.monster import Monster
from iris.structures.shop import Shop
from iris.tables import FormationObject, select, selected


_SEED = 1234
_LOW, _HIGH = -5, 10
_LOW_BYTE = 0xFB          # -5 in two's complement
_RANGE_BYTE = _HIGH - _LOW + 1
_BASE_ROM_SIZE = 3 * 1024 * 1024   # the unexpanded cart
# The roaming-monster formation store the patch hooks: STA.l $7FF8A4 at SNES $83:B9EC.
_HOOK_SITE = 0x01B9EC
_HOOK_VANILLA = b"\x8f\xa4\xf8\x7f"
_JSL = 0x22


def _reset_rom() -> None:
    """Restore the per-seed ROM, shrinking it back to the unexpanded cart.

    ``tests.reset_file.reset_file`` only rewrites the original bytes -- it does not truncate. This
    patch grows the ROM to 4MB, so without dropping the tail the next test would still see the
    reserved region occupied and the patch's own freespace guard would (correctly) refuse to bake.
    """
    data = original_file.read_bytes()
    write_file.seek(0)
    write_file.write(data)
    write_file.truncate(len(data))
    write_file.flush()


def test_average_level_ignores_empty_slots() -> None:
    formation = BattleFormation.from_table(FormationObject.address, 0)
    present = [m for m in formation.monsters if m.index != EMPTY_SLOT]
    assert present, "formation 0 should not be empty"
    assert formation.average_level == sum(m.stats.level for m in present) / len(present)


def test_average_level_is_none_when_every_slot_is_empty() -> None:
    empty = BattleFormation([Monster.from_index(EMPTY_SLOT) for _ in range(BattleFormation.max_monsters)])
    assert empty.average_level is None


def test_candidates_exclude_unused_and_boss_formations() -> None:
    indexes = {index for index, _ in _candidate_formations()}
    assert indexes.isdisjoint(UNUSED_FORMATIONS)
    assert indexes, "no formation is eligible for scaling"
    assert max(indexes) < FormationObject.count


def test_table_is_reproducible_and_well_formed() -> None:
    table = _build_level_table(random.Random(_SEED))
    assert table == _build_level_table(random.Random(_SEED))
    assert len(table) == SCALE_ENCOUNTERS_TABLE_SIZE == MAX_LEVEL - MIN_LEVEL + 1

    eligible = dict(_candidate_formations())
    assert all(formation in eligible for formation in table)

    # Every entry must be the best available match, up to the deliberate tie tolerance.
    for level, formation in enumerate(table, start=MIN_LEVEL):
        best = min(abs(average - level) for average in eligible.values())
        assert abs(eligible[formation] - level) <= best + TIE_TOLERANCE


def test_hook_site_holds_the_expected_vanilla_instruction() -> None:
    """The patch replaces a 4-byte STA.l with a 4-byte JSL, so the site must be what we think."""
    read_file.seek(_HOOK_SITE)
    assert read_file.read(4) == _HOOK_VANILLA


def test_bake_writes_the_reserved_region() -> None:
    try:
        table = _build_level_table(random.Random(_SEED))
        _write_scale_data(table, _LOW, _HIGH)
        write_file.flush()
        rom = output_bytes()

        assert rom[SCALE_ENCOUNTERS_TABLE:SCALE_ENCOUNTERS_TABLE + SCALE_ENCOUNTERS_TABLE_SIZE] == table
        assert rom[SCALE_ENCOUNTERS_LOW] == _LOW_BYTE
        assert rom[SCALE_ENCOUNTERS_RANGE] == _RANGE_BYTE
    finally:
        _reset_rom()


def test_full_patch_assembles_over_the_baked_data() -> None:
    try:
        scale_encounters(_LOW, _HIGH, _SEED)
        write_file.flush()
        rom = output_bytes()

        assert len(rom) == SCALE_ENCOUNTERS_ROM_SIZE, "the patch should expand the ROM to 4MB"
        # asar must not have disturbed the data written before it ran...
        assert rom[SCALE_ENCOUNTERS_LOW] == _LOW_BYTE
        assert rom[SCALE_ENCOUNTERS_RANGE] == _RANGE_BYTE
        # ...and it must have put the routine in the space reserved for it.
        code = rom[SCALE_ENCOUNTERS_CODE:SCALE_ENCOUNTERS_REGION.stop]
        assert any(code), "no code was assembled at the reserved code offset"
        # ...and hooked the roaming-monster formation store, replacing STA.l $7FF8A4 with a JSL.
        assert rom[_HOOK_SITE:_HOOK_SITE + 4] != _HOOK_VANILLA
        assert rom[_HOOK_SITE] == _JSL, "the hook site should now start with a JSL"
    finally:
        _reset_rom()


def test_reserved_region_is_blank_in_the_base_rom() -> None:
    """The region must be expansion space, not something the cart already uses.

    The base ROM is a full 3MB with almost no free space (notably EMPTY_BYTES[0] starts at 0x286a10,
    which holds real game data), so the reservation lives past the original end of the ROM.
    """
    assert SCALE_ENCOUNTERS_REGION.start >= _BASE_ROM_SIZE
    assert SCALE_ENCOUNTERS_REGION.stop <= SCALE_ENCOUNTERS_ROM_SIZE
    assert len(original_file.read_bytes()) <= _BASE_ROM_SIZE, "base ROM is larger than expected; re-check the reservation"


# --- Archipelago: switched per seed by the config block (Iris-Dev#25) ----------------------------

_HOOK_JSL = bytes([_JSL]) + address_to_lorom(SCALE_ENCOUNTERS_CODE).to_bytes(3, "little")


def _lda_long(offset: int) -> bytes:
    return bytes([0xAF]) + address_to_lorom(offset).to_bytes(3, "little")


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


@pytest.fixture(scope="module")
def ap_rom(source: bytes) -> Iterator[bytes]:
    """Built once for the module; module fixtures run before _restore_session, so this one restores its own."""
    rom, patch = session(), selected()
    verify_pointers, easy_mode = Shop.verify_pointers, Monster.easy_mode
    yield build(source, Options(1, selected_patch=Patch.VANILLA, archipelago=True, unlock_warps=False))
    Shop.verify_pointers, Monster.easy_mode = verify_pointers, easy_mode
    select(patch)
    use(rom)


def _code(rom: bytes) -> bytes:
    return rom[SCALE_ENCOUNTERS_CODE:SCALE_ENCOUNTERS_REGION.stop]


def test_archipelago_always_hooks_and_reads_the_config_block(ap_rom: bytes) -> None:
    assert ap_rom[_HOOK_SITE:_HOOK_SITE + 4] == _HOOK_JSL
    assert any(ap_rom[SCALE_ENCOUNTERS_TABLE:SCALE_ENCOUNTERS_TABLE + SCALE_ENCOUNTERS_TABLE_SIZE])
    code = _code(ap_rom)
    for offset in (AP_OPT_SCALING_ENABLED, AP_OPT_SCALING_LOW, AP_OPT_SCALING_RANGE):
        assert _lda_long(offset) in code, f"the hook doesn't read {offset:#x}"
    for offset in (SCALE_ENCOUNTERS_LOW, SCALE_ENCOUNTERS_RANGE):
        assert _lda_long(offset) not in code
    # Off by default, with the default band, so the base patch alone plays like vanilla.
    low, high = AP_DEFAULT_BAND
    assert ap_rom[AP_OPT_SCALING_ENABLED] == 0
    assert ap_rom[AP_OPT_SCALING_LOW] == low.to_bytes(1, "little", signed=True)[0]
    assert ap_rom[AP_OPT_SCALING_RANGE] == high - low + 1
    # Switched off, the hook replays the store and returns: STA.l $7FF8A4 : PHA : LDA.l enabled : BNE : PLA : PLP : RTL.
    off_path = bytes.fromhex("8F A4 F8 7F 48") + _lda_long(AP_OPT_SCALING_ENABLED) + bytes.fromhex("D0 03 68 28 6B 68")
    assert off_path in code


def test_plain_builds_keep_the_vanilla_store(source: bytes) -> None:
    rom = build(source, Options(1, selected_patch=Patch.VANILLA))
    assert rom[_HOOK_SITE:_HOOK_SITE + 4] == _HOOK_VANILLA


def test_cli_scaling_keeps_its_own_bytes_and_no_switch(source: bytes) -> None:
    rom = build(source, Options(1, selected_patch=Patch.VANILLA, scale_encounters=(_LOW, _HIGH)))
    assert rom[_HOOK_SITE:_HOOK_SITE + 4] == _HOOK_JSL
    assert rom[SCALE_ENCOUNTERS_LOW] == _LOW_BYTE
    assert rom[SCALE_ENCOUNTERS_RANGE] == _RANGE_BYTE
    code = _code(rom)
    assert _lda_long(SCALE_ENCOUNTERS_LOW) in code
    assert _lda_long(SCALE_ENCOUNTERS_RANGE) in code
    assert _lda_long(AP_OPT_SCALING_ENABLED) not in code
    # The routine opens straight into the swap: PHP : SEP #$20 : STA.l $7FF8A4 : REP #$30.
    assert code.startswith(bytes.fromhex("08 E2 20 8F A4 F8 7F C2 30"))
