"""Open world (Iris-Dev#43): terrorwave's open-world event patches, split so every NPC is its own patch.

``base.txt`` is absynnonym's ``eventpatch_open_world_base.txt`` without its NPCs. It expects the world at the end of
the story, so :func:`apply_open_world` applies ``eventpatch_max_world_clock.txt`` first. Each ``npc_*.txt`` replaces
its map's NPC-load script with base's plus that NPC, so it goes after the base. Event containers grow here: call
``structures.zone.move_all_zone_data`` first.
"""

from collections.abc import Iterable
from pathlib import Path

from iris.logger import iris
from iris.structures.event_script.event_patch import apply_event_patch_file


OPEN_WORLD = Path(__file__).parent
MAX_WORLD_CLOCK = OPEN_WORLD.parent / "absynnonym" / "eventpatch_max_world_clock.txt"
NPCS = (
    "npc_secondary_tool_tip",
    "npc_capsule_tips",
    "npc_tanbel_inn",
    "npc_cave_bridge_orb_guard",
    "npc_egg_key_trader",
    "npc_egg_wishes",
)
"""Each NPC patch, by file name. The Dankirk tip about terrorwave's Iris wards is left out: Iris has no Iris wards."""


def apply_open_world(npcs: Iterable[str] = ()) -> None:
    """Move every map to its end-of-story state, open the world, then add the chosen ``npcs`` (names from :data:`NPCS`)."""
    chosen = set(npcs)
    unknown = chosen - set(NPCS)
    if unknown:
        msg = f"Unknown open-world NPC patches: {sorted(unknown)}."
        raise ValueError(msg)
    iris.info("Applying open world.")
    apply_event_patch_file(MAX_WORLD_CLOCK)
    apply_event_patch_file(OPEN_WORLD / "base.txt")
    for npc in NPCS:  # in a fixed order, whatever order they were asked in
        if npc in chosen:
            apply_event_patch_file(OPEN_WORLD / f"{npc}.txt")
