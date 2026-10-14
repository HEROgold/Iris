"""Level-scale every normal enemy encounter to the party's current strength.

Vanilla spawns a fixed formation per roaming monster, so a map's difficulty never moves once you
outgrow it. This patch makes each non-boss battle roll a random offset inside a configurable
``[low, high]`` band, add it to the party's live average level, and swap the *pending* formation
(``$7F:F8A4``) for the one whose average monster level best matches that target.

Like the Ancient Cave basepatch this is a **hybrid** patch: the expensive part -- ranking all 192
formations by average monster level -- happens here in Python and is baked into the ROM as a flat
99-byte ``level -> formation id`` table plus the two roll constants, at the region carved out of
``constants.EMPTY_BYTES`` for exactly this purpose. ``scale_encounters.asm`` then only has to sum
four RAM bytes, roll one random number, and index the table, which keeps the injected 65816 tiny.

The candidate pool is every formation game-wide, not just the ones native to the current map, so a
high-level party may meet monsters that have nothing to do with where they are standing. That was
an explicit design decision: restricting to per-map pools leaves most levels with no usable match.

Excluded from the pool:
    * formation ``0xA5``    -- unused by the game (terrorwave notes it as dead data)
    * formations ``0xA7``-``0xAA`` -- the Ancient Cave "core" fights, which the game treats specially
    * formations whose slots are all empty
    * any formation containing a boss monster (index >= ``0xBC``), so bosses stay scripted-only

Boss and event battles are untouched at runtime as well. Only four instructions in the whole ROM
store to ``$7F:F8A4``, and the ASM hooks just one of them -- ``$83:B9EC``, the roaming map monster
you walk into. Scripted/boss battles (``$80:B919``, formation id read from the event stream) and
the Ancient Cave (``$86:9CE6``/``$86:9D5D``, which the game already level-scales itself) reach the
byte through a different store and never run our code. See ``scale_encounters.asm`` for the
disassembly behind each of those four sites.
"""

import random
from pathlib import Path

from iris.constants import (
    AP_OPT_SCALING_ENABLED,
    AP_OPT_SCALING_LOW,
    AP_OPT_SCALING_RANGE,
    EXPANDED_ROM_SIZE,
    SCALE_ENCOUNTERS_LOW,
    SCALE_ENCOUNTERS_MAX_BAND,
    SCALE_ENCOUNTERS_MAX_OFFSET,
    SCALE_ENCOUNTERS_RANGE,
    SCALE_ENCOUNTERS_REGION,
    SCALE_ENCOUNTERS_ROM_SIZE,
    SCALE_ENCOUNTERS_TABLE,
    SCALE_ENCOUNTERS_TABLE_SIZE,
)
from iris.helpers.addresses import address_to_lorom
from iris.helpers.files import write_file
from iris.helpers.rom_expansion import assert_region_blank, ensure_rom_expanded
from iris.logger import iris
from iris.patcher import apply_asm_patch
from iris.structures.formation import EMPTY_SLOT, BattleFormation
from iris.tables import FormationObject


_ASM = Path(__file__).parent/"scale_encounters.asm"

MIN_LEVEL = 1
MAX_LEVEL = 99
"""The game's playable level range; the baked table covers it exactly, so the ASM cannot index OOB."""

FIRST_BOSS_MONSTER = 0xBC
"""Monsters from this index up are bosses/uniques and must never appear in a random encounter."""

UNUSED_FORMATIONS = frozenset({0xA5, *range(0xA7, 0xAB)})
"""Dead data (0xA5) and the special Ancient Cave core fights (0xA7-0xAA)."""

TIE_TOLERANCE = 0.5
"""Formations within this many levels of the best match are treated as equally good, and one is
picked at random. Without it every level would deterministically collapse onto a single formation
and whole stretches of the game would reuse the same fight."""


def _candidate_formations() -> list[tuple[int, float]]:
    """Every formation eligible as a random encounter, as ``(index, average monster level)``."""
    candidates: list[tuple[int, float]] = []
    for index in range(FormationObject.count):
        if index in UNUSED_FORMATIONS:
            continue
        # Read the row's raw slots rather than BattleFormation.from_table: that would build a
        # Monster per slot and parse its AI script, which still raises KeyError for opcodes the
        # incomplete opcode table did not cover.
        slots = BattleFormation.monster_indexes(FormationObject.address, index)
        if any(slot != EMPTY_SLOT and slot >= FIRST_BOSS_MONSTER for slot in slots):
            continue
        average = BattleFormation.average_level_of(FormationObject.address, index)
        if average is None:  # every slot empty
            continue
        candidates.append((index, average))
    if not candidates:
        msg = "No formations are eligible for level scaling; the formation table looks corrupt."
        raise ValueError(msg)
    return candidates


def _build_level_table(rng: random.Random) -> bytes:
    """Pick one formation id per level 1..99, closest by average monster level.

    One id per level keeps the ASM a plain indexed load; the per-battle variety comes from the
    runtime offset roll, which spreads consecutive fights across neighbouring table entries.
    """
    candidates = _candidate_formations()
    table = bytearray()
    for level in range(MIN_LEVEL, MAX_LEVEL + 1):
        best = min(abs(average - level) for _, average in candidates)
        close = [index for index, average in candidates if abs(average - level) <= best + TIE_TOLERANCE]
        table.append(rng.choice(close))
    assert len(table) == SCALE_ENCOUNTERS_TABLE_SIZE
    return bytes(table)


def _write_scale_data(table: bytes, low: int, high: int) -> None:
    """Bake the lookup table and the roll constants into the reserved region.

    The ``.asm`` grows the ROM too, but asar only runs *after* this data is baked, so the file has
    to be the right size first -- otherwise the seek below would leave a ragged, undersized ROM for
    asar to read.
    """
    ensure_rom_expanded(SCALE_ENCOUNTERS_ROM_SIZE)
    assert_region_blank(SCALE_ENCOUNTERS_REGION, owner="scale_encounters")
    write_file.seek(SCALE_ENCOUNTERS_TABLE)
    write_file.write(table)
    write_file.seek(SCALE_ENCOUNTERS_LOW)
    write_file.write(low.to_bytes(1, "little", signed=True))
    write_file.seek(SCALE_ENCOUNTERS_RANGE)
    write_file.write((high - low + 1).to_bytes(1, "little"))


AP_TABLE_SEED = 0
"""The Archipelago base patch is static, so its level table is always baked from this seed."""
AP_DEFAULT_BAND = (-2, 2)
"""The band the Archipelago base patch carries until the world's tokens set one (the apworld's defaults)."""


def _check_band(low: int, high: int) -> None:
    limit = SCALE_ENCOUNTERS_MAX_OFFSET
    if not (-limit <= low <= high <= limit):
        msg = f"Encounter scaling band must satisfy {-limit} <= low <= high <= {limit}, got {low}..{high}."
        raise ValueError(msg)
    if high - low + 1 > SCALE_ENCOUNTERS_MAX_BAND:
        msg = (f"Encounter scaling band spans {high - low + 1} levels, "
               f"more than the {SCALE_ENCOUNTERS_MAX_BAND} the ROM can store.")
        raise ValueError(msg)


def scale_encounters(low: int, high: int, seed: int) -> None:
    """Scale normal encounters to the party's average level, offset by a roll in ``[low, high]``.

    ``seed`` makes the baked level table reproducible.
    """
    _check_band(low, high)
    iris.info(f"Scaling normal encounters to party level, offset by [{low}, {high}].")
    # A dedicated Random keeps the table reproducible from the seed alone, independent of how much
    # of the global `random` stream earlier patches happened to consume.
    table = _build_level_table(random.Random(seed))
    _write_scale_data(table, low, high)
    # asar runs last so its checksum fix covers the data written above.
    apply_asm_patch(_ASM)


def install_ap_encounter_scaling() -> None:
    """The Archipelago base patch's encounter scaling: the table and the hook, switched by the config block.

    The table is baked from :data:`AP_TABLE_SEED` so the base patch stays static. The hook reads the on/off byte and
    the band from ``AP_OPT_SCALING_*`` instead of ``$E2:8063/8064``, and with the byte at 0 leaves the vanilla
    formation alone. :func:`write_ap_scaling_defaults` fills those bytes once the config block exists.
    """
    iris.info("Installing encounter scaling, switched per seed by the Archipelago config block.")
    table = _build_level_table(random.Random(AP_TABLE_SEED))
    ensure_rom_expanded(SCALE_ENCOUNTERS_ROM_SIZE)
    assert_region_blank(SCALE_ENCOUNTERS_REGION, owner="scale_encounters")
    write_file.seek(SCALE_ENCOUNTERS_TABLE)
    write_file.write(table)
    apply_asm_patch(_ASM, defines={
        "enabled_byte": f"${address_to_lorom(AP_OPT_SCALING_ENABLED):06X}",
        "low_byte": f"${address_to_lorom(AP_OPT_SCALING_LOW):06X}",
        "range_byte": f"${address_to_lorom(AP_OPT_SCALING_RANGE):06X}",
    })


def write_ap_scaling_defaults(low: int, high: int, *, enabled: bool = False) -> None:
    """Write the config block's scaling bytes: on/off, the band's low end (two's complement) and its size."""
    _check_band(low, high)
    ensure_rom_expanded(EXPANDED_ROM_SIZE)
    write_file.seek(AP_OPT_SCALING_ENABLED)
    write_file.write(bytes([int(enabled)]))
    write_file.seek(AP_OPT_SCALING_LOW)
    write_file.write(low.to_bytes(1, "little", signed=True))
    write_file.seek(AP_OPT_SCALING_RANGE)
    write_file.write((high - low + 1).to_bytes(1, "little"))
