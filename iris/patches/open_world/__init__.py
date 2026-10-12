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
from iris.patches.open_world.leader import reserve_leader_room
from iris.structures.event_script.compiler import compile_script
from iris.structures.event_script.containers import MapEvent
from iris.structures.event_script.event_patch import apply_event_patch_file, measure_event_patch, resolve_or_create
from iris.structures.event_script.instructions import Instruction
from iris.structures.zone import NPC, Boundary, Zone
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


END = 0x00
NPC_SIZE = len(bytes(NPC(1, 0, 0, Boundary(0, 0, 1, 1), 0)))


def reserve_extras_room() -> None:
    """Give every map an event-patch extra touches room for it, so applying the extra later changes bytes in place.

    For the Archipelago open-world base patch (Iris-Dev#43), whose extras are per-seed byte diffs on top of it: each such
    map's event container moves into a block of its own where every script the extras replace has a slot big enough
    for its biggest version (theirs or the one already there) (the scripts they add exist as an empty ``END``), and its ZoneData gets room for the NPCs
    they add. Without this an extra grows its container, which moves to wherever the pool has room, and everything
    allocated after it moves too. Nothing changes in the game: the added scripts belong to NPCs that aren't there.
    """
    sizes: dict[str, int] = {}
    npcs: dict[int, int] = {}
    for name in EXTRAS:
        path = OPEN_WORLD / f"{name}.txt"
        if not path.exists():
            continue
        patch_sizes, patch_npcs = measure_event_patch(path.read_text(encoding="utf-8"))
        for signature, size in patch_sizes.items():
            sizes[signature] = max(sizes.get(signature, 0), size)
        for map_index, count in patch_npcs.items():
            npcs[map_index] = npcs.get(map_index, 0) + count
    for map_index in sorted({int(signature[:2], 16) for signature in sizes}):
        for signature, size in sizes.items():
            if int(signature[:2], 16) != map_index:
                continue
            script = resolve_or_create(signature)
            if not script.instructions:
                script.instructions = [Instruction(0, END, [])]
            current = len(compile_script(script, ignore_pointers=True, compress=True))
            script.min_slot = max(script.min_slot, size, current)
            script.slack = script.min_slot - current
        MapEvent.from_index(map_index).reserve()
        if map_index in npcs:
            Zone.from_index(map_index).data.reserve(map_index, npcs[map_index] * NPC_SIZE)


def apply_open_world(extras: Iterable[str] = (), *, reserve: bool = False) -> None:
    """Move every map to its end-of-story state, open the world, then apply the chosen ``extras`` (from :data:`EXTRAS`).

    With ``reserve`` (the Archipelago open-world base), the ROM gets room for every extra and every leader first
    (:func:`reserve_extras_room`, ``leader.reserve_leader_room``), so each of them is a small in-place diff.
    """
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
    if reserve:
        reserve_extras_room()
        reserve_leader_room()
    for name, apply in EXTRAS.items():  # in a fixed order, whatever order they were asked in
        if name in chosen:
            apply()
