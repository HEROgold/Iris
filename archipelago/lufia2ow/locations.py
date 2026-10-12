"""Locations: the red chests (named from guides) and the script grants that set a flag the client can read.

Chest id = BASE_ID + chest index; grant id = GRANT_BASE + its row in ``data.GRANTS``; an open-world boss reward's id is
BOSS_BASE + 2 * its spot's row in ``data_open_world.BOSS_NPCS`` + the reward's number (0, 1); the open-world orb check's
is ORB_CHECK_ID. The Ancient Cave and the
Dragon Egg shrine's wishes stay vanilla (see ``logic``); blue chests come with Iris-Dev#21.
"""

from types import ModuleType
from typing import NamedTuple

from BaseClasses import Location

from . import data, data_open_world
from .items import BASE_ID, GAME, ITEM_NAMES
from .logic import EXCLUDED_GRANTS, EXCLUDED_MAPS


GRANT_BASE = BASE_ID + 0x1000
BOSS_BASE = BASE_ID + 0x2000
ORB_CHECK_ID = BASE_ID + 0x3000


class LocationInfo(NamedTuple):
    name: str
    code: int
    map_index: int
    vanilla_item: int
    grant: str | None
    """The grant's event signature, for grants; None for chests."""


MAP_NAME_FALLBACK = {
    **dict.fromkeys(range(0x61, 0x68), "Phantom Tree Mountain"),
    **{0xD2: "Gratze Castle B1", 0xD3: "Gratze Castle B2", 0xD4: "Gratze Castle B3", 0xD5: "Gratze Castle B4"},
    **{0xD6: "Gratze Kingdom", 0xD7: "Gratze Kingdom", 0xDC: "Shuman Tower", 0xE0: "Strahda Tower", 0xE4: "Kamirno Tower"},
}
"""Maps whose own name doesn't decode fully (Phantom Tree Mountain reads "Phant") or is blank in the ROM."""


def place(map_index: int) -> str:
    return MAP_NAME_FALLBACK.get(map_index) or data.MAP_NAMES.get(map_index) or f"Map {map_index:#04x}"


def _grant_name(map_index: int, item: int) -> str:
    return f"{place(map_index)}: {ITEM_NAMES.get(item, str(item))} reward"


def _chest_name(map_index: int, guide_name: str) -> str:
    """The game's map name, then the chest's position and vanilla item from the guide name (Iris chest_names)."""
    return f"{place(map_index)}, {guide_name.split(', ', 1)[1]}"


def _locations() -> list[LocationInfo]:
    out = [
        LocationInfo(_chest_name(map_index, name), BASE_ID + index, map_index, item, None)
        for index, map_index, name, _, _, item in data.CHESTS
        if map_index not in EXCLUDED_MAPS
    ]
    counts: dict[str, int] = {}
    for info in out:
        counts[info.name] = counts.get(info.name, 0) + 1
    out = [info._replace(name=f"{info.name} [map {info.map_index:#04x}]") if counts[info.name] > 1 else info for info in out]
    for row, (map_index, signature, _, item, _, flags) in enumerate(data.GRANTS):
        if flags and signature not in EXCLUDED_GRANTS and map_index not in EXCLUDED_MAPS:
            out.append(LocationInfo(_grant_name(map_index, item), GRANT_BASE + row, map_index, item, signature))
    return out


LOCATIONS = _locations()
location_name_to_id = {location.name: location.code for location in LOCATIONS}
GRANT_FLAGS = {info.code: data.GRANTS[info.code - GRANT_BASE][5][0] for info in LOCATIONS if info.grant is not None}
"""Grant location id -> the event flag its script sets, which the client reads as the check."""


def grant_offsets(module: ModuleType) -> dict[int, int]:
    """Grant location id -> the offset of its item byte in ``module`` (``data`` or ``data_open_world``).

    A grant is the n-th grant of its script in both modules. Open world replaces some story scripts with ones that grant
    nothing; their grants are missing from ``data_open_world.GRANTS`` and from this map.
    """

    def keyed(rows: list) -> dict[tuple[int, str, int], tuple[int, int]]:
        seen: dict[tuple[int, str], int] = {}
        out = {}
        for row, (map_index, signature, offset, *_) in enumerate(rows):
            n = seen.get((map_index, signature), 0)
            seen[map_index, signature] = n + 1
            out[map_index, signature, n] = (row, offset)
        return out

    offsets = {key: offset for key, (_, offset) in keyed(module.GRANTS).items()}
    return {GRANT_BASE + row: offsets[key] for key, (row, _) in keyed(data.GRANTS).items() if key in offsets}


class BossReward(NamedTuple):
    """An open-world boss NPC's reward: a ``20`` grant in its talk script, checked by the boss's beaten flag."""

    name: str
    code: int
    map_index: int
    flag: int
    offset: int
    """The grant's item byte in the open-world base ROM (``rom.write_grant``)."""


def _boss_rewards() -> list[BossReward]:
    """Every boss spot's rewards, Daos (no reward) left out: "<Spot> Boss", and "<Spot> Boss 2" for a second one."""
    out = []
    for row, (spot, map_index, flag, _, _, _, _, offsets) in enumerate(data_open_world.BOSS_NPCS):
        title = spot.replace("_", " ").title()
        for n, offset in enumerate(offsets):
            name = f"{title} Boss" if n == 0 else f"{title} Boss {n + 1}"
            out.append(BossReward(name, BOSS_BASE + 2 * row + n, map_index, flag, offset))
    return out


BOSS_REWARDS = _boss_rewards()
location_name_to_id |= {reward.name: reward.code for reward in BOSS_REWARDS}
BOSS_FLAGS = {reward.code: reward.flag for reward in BOSS_REWARDS}
"""Boss reward location id -> the boss's beaten flag; a boss with two rewards sends both when it's set."""

_ORB_MAP, _, ORB_CHECK_ITEM, _ORB_FLAG = data_open_world.ORB_CHECK
ORB_CHECK = LocationInfo(f"{place(_ORB_MAP)}: Orb", ORB_CHECK_ID, _ORB_MAP, ORB_CHECK_ITEM, None)
"""Open world with Cave Bridge Orb orb_check: touching the orb is a grant (``data_open_world.ORB_CHECK``)."""
location_name_to_id[ORB_CHECK.name] = ORB_CHECK.code
ORB_FLAGS = {ORB_CHECK.code: _ORB_FLAG}
"""The orb check's location id -> the flag its script sets (0x30, vanilla's "orb touched", which nothing else reads in
open world; in the linear game the location doesn't exist, so the client never sends it)."""


class L2OWLocation(Location):
    game = GAME
