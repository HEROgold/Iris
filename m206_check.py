"""Throwaway: build the HER-206 emulator check ROMs (moved ZoneData). Not committed.

Baseline: the normal --debug build (spawns in Elcid). Checks (--edits): the ZoneData of Elcid (3), Elcid's interiors (4)
and the cave toward Sundletan (6) moved into the ZONE_DATA_FREESPACE pool (bank $E4) by ZoneData.write_relocated, and
Elcid's world-map exit pointed at the spot outside that cave, so leaving Elcid only lands there if the game reads the
moved copy.
"""

import shutil
import sys
from pathlib import Path

EDIT = "--edits" in sys.argv
if EDIT:
    sys.argv.remove("--edits")

source = Path("__main__.py").read_text(encoding="utf-8").split('if __name__ == "__main__":')[0]
ns: dict[str, object] = {"__name__": "iris_main"}
exec(compile(source, "__main__.py", "exec"), ns)  # noqa: S102
ns["main"]()  # type: ignore[operator]

from helpers.addresses import address_to_lorom  # noqa: E402
from helpers.files import new_file, save, write_file  # noqa: E402
from structures.map_meta import MapMeta  # noqa: E402
from structures.zone import ZONE_DATA_POINTER_TABLE  # noqa: E402

ELCID, INTERIORS, CAVE = 3, 4, 6
WORLD_MAP = 0
OUTSIDE_CAVE = (47, 197)  # where map 6's exit puts you on the world map

report = []
if EDIT:
    for index in (ELCID, INTERIORS, CAVE):
        zone_data = MapMeta.from_index(index).zone_data
        before = (list(zone_data.exits), list(zone_data.npc_positions), list(zone_data.chests))
        if index == ELCID:
            world_exit = next(e for e in zone_data.exits if e.destination_map == WORLD_MAP)
            world_exit.destination_x, world_exit.destination_y = OUTSIDE_CAVE
        old = zone_data.start
        zone_data.write_relocated(index)
        # The output ROM holds the moved blob, and the map's pointer-table entry points at it.
        write_file.seek(zone_data.start)
        assert write_file.read(zone_data.size + 2) == zone_data.rebuild()
        write_file.seek(ZONE_DATA_POINTER_TABLE + 3 * index)
        assert int.from_bytes(write_file.read(3), "little") == address_to_lorom(zone_data.start)
        report.append(
            f"map {index}: {old:#x} -> {zone_data.start:#x} (${address_to_lorom(zone_data.start):06X}), "
            f"{len(zone_data.exits)} exits, {len(zone_data.npc_positions)} NPCs, {len(zone_data.chests)} chests"
        )
        report.append(f"  chests: {zone_data.chests}")
        assert before[1] == zone_data.npc_positions
        assert before[2] == zone_data.chests

write_file.flush()
name = "her206-checks" if EDIT else "her206-baseline"
target = new_file.with_name(f"{name}-{new_file.stem.rsplit('-', 1)[1]}.smc")
save(target)
Path("m206_check_report.txt").write_text("\n".join(report), encoding="utf-8")
print(target)  # noqa: T201
