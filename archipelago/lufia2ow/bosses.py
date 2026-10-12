"""Open world's boss placement and boss strength (Iris-Dev#43): which boss stands at each boss spot, and the levels
the ROM's boss-scaling hook (Iris ``scale_bosses.asm``) scales scripted battles to.

A placement is a list of rows of ``data_open_world.BOSSES``, one per spot of ``BOSS_SPOTS`` (story order); Daos always
guards ``FINAL_SPOT`` and isn't in it. Ported from Iris ``iris/patches/open_world/bosses.py``.
"""

import random

from . import data_open_world as data


Boss = tuple[str, int, int, int, int]
"""A row of ``data_open_world.BOSSES``: (name, sprite, formation, bgm, power)."""
SHUFFLE_SPREAD = 0.25
"""How far a shuffled boss may move from its story position, as a share of all spots (Iris's SHUFFLE_SPREAD)."""
STRENGTH_LEVELS = data.CONFIG["AP_OPT_BOSS_LEVELS_SIZE"]
"""The level table's size: one byte per formation byte; formations past it aren't scaled."""
MIN_LEVEL, MAX_LEVEL = 1, 99


def fixed_placement() -> list[Boss]:
    """The base patch's placement: each spot gets the boss at the same place in story order."""
    bosses, spots = data.BOSSES, data.BOSS_SPOTS
    return [bosses[index * len(bosses) // len(spots)] for index in range(len(spots))]


def shuffled_placement(rng: random.Random) -> list[Boss]:
    """Iris's ``shuffled_placement``: every boss once plus random repeats for the spots past them, in story order,
    each moved a random distance of at most SHUFFLE_SPREAD of the spots, then sorted (early spots tend to stay early)."""
    bosses, spots = data.BOSSES, data.BOSS_SPOTS
    pool = list(bosses) + rng.sample(bosses, len(spots) - len(bosses))
    pool.sort(key=bosses.index)
    spread = SHUFFLE_SPREAD * len(spots)
    order = sorted(range(len(pool)), key=lambda i: i + rng.uniform(-spread, spread))
    return [pool[i] for i in order]


def depth_levels(placement: list[Boss]) -> bytes:
    """``AP_OPT_BOSS_LEVELS`` for by_depth: per formation byte, the mean power of the story's bosses at the spots
    the placed boss stands at (Iris's ``scale_to_depth``); 0 (unchanged) for formations not placed, Daos included."""
    story = fixed_placement()
    targets: dict[int, list[int]] = {}
    for spot, boss in enumerate(placement):
        targets.setdefault(boss[2], []).append(story[spot][4])
    levels = bytearray(STRENGTH_LEVELS)
    for formation, powers in targets.items():
        if formation < STRENGTH_LEVELS:
            levels[formation] = min(max(round(sum(powers) / len(powers)), MIN_LEVEL), MAX_LEVEL)
    return bytes(levels)
