"""Tests for --scale-encounters: the baked level->formation table and the asar half of the patch.

The runtime behaviour (does a fight actually get swapped?) needs an emulator. What is testable here
is that the Python side bakes a well-formed, reproducible table into the reserved region, that the
region is real expansion space, that asar's output leaves the baked data intact, and that the hook
lands on the instruction we expect -- so the site cannot silently drift onto the wrong bytes.
"""

import random

from constants import (
    SCALE_ENCOUNTERS_CODE,
    SCALE_ENCOUNTERS_LOW,
    SCALE_ENCOUNTERS_RANGE,
    SCALE_ENCOUNTERS_REGION,
    SCALE_ENCOUNTERS_ROM_SIZE,
    SCALE_ENCOUNTERS_TABLE,
    SCALE_ENCOUNTERS_TABLE_SIZE,
)
from helpers.files import original_file, output_bytes, read_file, write_file
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
        scale_encounters(_LOW, _HIGH)
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
