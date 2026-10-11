"""Open world (Iris-Dev#43): terrorwave's open-world event patches, split so every extra is its own patch.

``base.txt`` is absynnonym's ``eventpatch_open_world_base.txt`` without its NPCs. It expects the world at the end of
the story, so :func:`apply_open_world` applies ``eventpatch_max_world_clock.txt`` first. Each extra in :data:`EXTRAS` is
optional; an ``npc_*`` one replaces its map's NPC-load script with base's plus that NPC, so extras go after the base.
Event containers grow here: call ``structures.zone.move_all_zone_data`` first.
"""

from collections.abc import Callable, Iterable
from functools import partial
from pathlib import Path

from iris.logger import iris
from iris.structures.event_script.containers import MapEvent
from iris.structures.event_script.event_patch import apply_event_patch_file
from iris.tables import MapEventObject


OPEN_WORLD = Path(__file__).parent
MAX_WORLD_CLOCK = OPEN_WORLD.parent / "absynnonym" / "eventpatch_max_world_clock.txt"
MAP_PROPERTIES = 0x69
NO_ESCAPE = 0x08
"""Bit of a ``69`` (map properties) operand that forbids Escape and Warp on the map (terrorwave's NO_ESCAPE_BIT)."""
INESCAPABLE_MAPS = frozenset((0x00, 0x01, *range(0x75, 0x79), *range(0xE6, 0xED)))
"""The overworld, the seafloor, Karlloon Shrine and Daos' Shrine stay as they are, as in terrorwave."""


def escapable_dungeons() -> None:
    """Every map can be left with Escape or Warp, except :data:`INESCAPABLE_MAPS` (terrorwave's change_escapability)."""
    for index in range(MapEventObject.count):
        map_event = MapEvent.from_index(index)
        script = map_event.npc_script
        escapable = index not in INESCAPABLE_MAPS
        for instruction in script.instructions:
            if instruction.opcode != MAP_PROPERTIES:
                continue
            value = instruction.operands[0]
            assert isinstance(value, int)
            new = value & ~NO_ESCAPE if escapable else value | NO_ESCAPE
            if new != value:
                instruction.operands[0] = new
                script.dirty = True
        if script.dirty:
            map_event.write()


def _event_patch(name: str) -> Callable[[], None]:
    return partial(apply_event_patch_file, OPEN_WORLD / f"{name}.txt")


EXTRAS: dict[str, Callable[[], None]] = {
    "npc_secondary_tool_tip": _event_patch("npc_secondary_tool_tip"),
    "npc_capsule_tips": _event_patch("npc_capsule_tips"),
    "npc_tanbel_inn": _event_patch("npc_tanbel_inn"),
    "npc_cave_bridge_orb_guard": _event_patch("npc_cave_bridge_orb_guard"),
    "npc_egg_key_trader": _event_patch("npc_egg_key_trader"),
    "npc_egg_wishes": _event_patch("npc_egg_wishes"),
    "orb_check": _event_patch("orb_check"),
    "escapable_dungeons": escapable_dungeons,
}
"""Every optional open-world patch by name, applied in this order. The Dankirk tip about terrorwave's Iris wards is left
out (Iris has no Iris wards). ``orb_check`` puts an item where the orb guard would stand, so they don't go together;
the orb doesn't crash the game in Iris (checked in Mesen), so the guard is only kept for terrorwave parity."""
EXCLUSIVE = (frozenset(("npc_cave_bridge_orb_guard", "orb_check")),)


def apply_open_world(extras: Iterable[str] = ()) -> None:
    """Move every map to its end-of-story state, open the world, then apply the chosen ``extras`` (from :data:`EXTRAS`)."""
    chosen = set(extras)
    unknown = chosen - EXTRAS.keys()
    if unknown:
        msg = f"Unknown open-world extras: {sorted(unknown)}."
        raise ValueError(msg)
    for group in EXCLUSIVE:
        if group <= chosen:
            msg = f"Open-world extras {sorted(group)} can't be used together."
            raise ValueError(msg)
    iris.info("Applying open world.")
    apply_event_patch_file(MAX_WORLD_CLOCK)
    apply_event_patch_file(OPEN_WORLD / "base.txt")
    for name, apply in EXTRAS.items():  # in a fixed order, whatever order they were asked in
        if name in chosen:
            apply()
