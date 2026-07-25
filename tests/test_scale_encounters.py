"""Tests for --scale-encounters: the baked level->formation table and the asar half of the patch.

The runtime behaviour (does a fight actually get swapped?) cannot be tested here -- see the
"STILL TO CONFIRM IN AN EMULATOR" block at the top of scale_encounters.asm. What is testable is
that the Python side bakes a well-formed, reproducible table into the reserved region and that the
region survives assembly.
"""

import random

from constants import (
    EMPTY_BYTES,
    SCALE_ENCOUNTERS_CODE,
    SCALE_ENCOUNTERS_LOW,
    SCALE_ENCOUNTERS_RANGE,
    SCALE_ENCOUNTERS_REGION,
    SCALE_ENCOUNTERS_TABLE,
    SCALE_ENCOUNTERS_TABLE_SIZE,
)
from helpers.files import new_file, read_file, write_file
from patches.HEROgold.scale_encounters import (
    MAX_LEVEL,
    MIN_LEVEL,
    TIE_TOLERANCE,
    UNUSED_FORMATIONS,
    _build_level_table,
    _candidate_formations,
    _write_scale_data,
    scale_encounters,
)
from structures.formation import EMPTY_SLOT, BattleFormation
from structures.monster import Monster
from tables import FormationObject
from tests.reset_file import reset_file


_SEED = 1234
_LOW, _HIGH = -5, 10
_LOW_BYTE = 0xFB          # -5 in two's complement
_RANGE_BYTE = _HIGH - _LOW + 1
_THREE_MB = 3 * 1024 * 1024
# The roaming-monster formation store the patch hooks: STA.l $7FF8A4 at SNES $83:B9EC.
_HOOK_SITE = 0x01B9EC
_HOOK_VANILLA = b"\x8f\xa4\xf8\x7f"
_JSL = 0x22


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
        rom = new_file.read_bytes()

        assert rom[SCALE_ENCOUNTERS_TABLE:SCALE_ENCOUNTERS_TABLE + SCALE_ENCOUNTERS_TABLE_SIZE] == table
        assert rom[SCALE_ENCOUNTERS_LOW] == _LOW_BYTE
        assert rom[SCALE_ENCOUNTERS_RANGE] == _RANGE_BYTE
    finally:
        reset_file()


def test_full_patch_assembles_over_the_baked_data() -> None:
    try:
        scale_encounters(_LOW, _HIGH)
        write_file.flush()
        rom = new_file.read_bytes()

        assert len(rom) >= _THREE_MB, "the patch should pad the ROM out to 3MB"
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
        reset_file()


def test_reserved_region_is_carved_out_of_the_freespace_pool() -> None:
    assert EMPTY_BYTES[0].start == SCALE_ENCOUNTERS_REGION.stop
    assert all(SCALE_ENCOUNTERS_REGION.start not in region for region in EMPTY_BYTES)
