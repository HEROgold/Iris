"""Phase 5 of the map-content strategy: add/remove a map NPC as one unit, using the
freespace/allocator work from Phases 1-4 (ZoneData growth, event-container relocation).

**Important finding from building this (not documented anywhere else before now):** a ZoneData
section-7 NPC *position* record's ``index`` and the "NPC slot" used by a map's ``0x68`` sprite-load
instruction / ``REFERENCED`` talk-script index are **two independent numbering spaces with no
confirmed relationship**. Checked against real data (Elcid, map ``0x03``): 13 position records
(index 1-13) vs only 10 distinct ``0x68`` slot values (``0x50,0x51,0x52,0x53,0x56,0x57,0x58,0x59,
0x5A,0x5C``) -- different counts, and neither an arithmetic offset nor a positional-order match
lines them up. This is the same kind of open question as the chest x/y placement caveat in the
lufia2-object-layout skill (section-18 chest coords vs content records): real, unconfirmed, and out
of scope to resolve here. The only place that actually builds one of these correspondences today,
`patches/HEROgold/party_toggle.py`, hand-picks known-good slot values for one specific map (Elcid);
it doesn't derive them from ZoneData, because nothing establishes that derivation.

Consequently this module does **not** attempt to enumerate or validate existing vanilla NPCs --
there is no reliable way to say "position record N is drawn by sprite-load instruction M" for data
Iris didn't create itself. It only supports building a **new**, self-consistent NPC: a position
record and an NPC slot Iris chooses together, so there is nothing to reconcile -- they agree because
they were made to agree, not because some pre-existing rule was discovered and checked.

Also out of scope: `RoamingNPCObject` (`structures.npc.RoamingNPC`). It's a fixed 34-entry global
table with no allocator of its own (unlike ZoneData/event scripts, nothing reserves growable space
for it), and which numbering space its `map_npc_index` even corresponds to is exactly the same open
question as above. Not touched by `add_npc`/`remove_npc`.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from enums.event_scripts import EventClass
from structures.event_script.instructions import Instruction
from structures.event_script.script import EventScript
from structures.zone import NPC, Boundary


if TYPE_CHECKING:
    from structures.zone import Zone


NPC_SPRITE_OPCODE = 0x68
DEFAULT_SLOT_FLOOR = 0x4F  # every observed 0x68 slot in this ROM is 0x50 or above; see module docstring


@dataclass
class MapNpc:
    """One NPC Iris created: its ZoneData position record, sprite-load instruction, and (optional)
    talk script, built together by :func:`add_npc` -- so, unlike general vanilla data (see this
    module's docstring), these three are guaranteed to actually belong to each other."""

    zone: "Zone"
    position: NPC
    npc_slot: int
    sprite_instruction: Instruction
    talk_script: EventScript | None


def _next_position_index(zone: "Zone") -> int:
    return max((npc.index for npc in zone.data.npc_positions), default=0) + 1


def _next_npc_slot(zone: "Zone") -> int:
    """The next NPC slot not already used by any ``0x68`` instruction on this map."""
    used: set[int] = set()
    for instruction in zone.event.npc_script.instructions:
        if instruction.opcode == NPC_SPRITE_OPCODE:
            slot = instruction.operands[0]
            assert isinstance(slot, int)
            used.add(slot)
    return max(used, default=DEFAULT_SLOT_FLOOR) + 1


def add_npc(
    zone: "Zone",
    x: int,
    y: int,
    sprite_index: int,
    *,
    boundary: Boundary | None = None,
    misc: int = 0,
    npc_slot: int | None = None,
    talk_instructions: list[Instruction] | None = None,
) -> MapNpc:
    """Add a new NPC to ``zone`` at ``(x, y)``: a ZoneData position record, a sprite-load
    instruction, and (if ``talk_instructions`` is given) a new talk script.

    ``npc_slot`` picks the NPC slot for the sprite load / talk-script index; defaults to the next
    unused slot on this map (see :func:`_next_npc_slot`). Marks ``zone.data`` and the NPC-load
    script (and the REFERENCED event list, if a talk script was added) dirty -- a caller still needs
    to persist those through the normal write path (``MapMeta.write()`` /
    ``zone.write_events()``), exactly like every other ``set_*`` mutator in this codebase.
    """
    position = NPC(_next_position_index(zone), x, y, boundary or Boundary(0, 0, 0, 0), misc)
    zone.data.set_npcs([*zone.data.npc_positions, position])

    slot = npc_slot if npc_slot is not None else _next_npc_slot(zone)
    npc_script = zone.event.npc_script
    sprite_instruction = Instruction(
        line=max((instruction.line for instruction in npc_script.instructions), default=-1) + 1,
        opcode=NPC_SPRITE_OPCODE,
        operands=[slot, sprite_index],
    )
    npc_script.instructions.append(sprite_instruction)
    npc_script.dirty = True

    talk_script = None
    if talk_instructions is not None:
        talk_script = EventScript(0, 0, slot, EventClass.REFERENCED)
        talk_script.instructions = list(talk_instructions)
        talk_script.dirty = True
        talk_script._read = True  # noqa: SLF001 -- brand new, nothing to read from ROM
        referenced_list = next(el for el in zone.event.event_lists if el.event_class is EventClass.REFERENCED)
        referenced_list.events.append(talk_script)

    return MapNpc(zone, position, slot, sprite_instruction, talk_script)


def remove_npc(npc: MapNpc) -> None:
    """Remove everything :func:`add_npc` created for ``npc``: its position record, sprite-load
    instruction, and talk script (if any). Only meaningful for an ``npc`` :func:`add_npc` returned
    -- see this module's docstring for why an arbitrary vanilla NPC can't be looked up this way.
    """
    zone = npc.zone
    zone.data.set_npcs([position for position in zone.data.npc_positions if position.index != npc.position.index])

    npc_script = zone.event.npc_script
    npc_script.instructions.remove(npc.sprite_instruction)
    npc_script.dirty = True

    if npc.talk_script is not None:
        referenced_list = next(el for el in zone.event.event_lists if el.event_class is EventClass.REFERENCED)
        referenced_list.events.remove(npc.talk_script)
        referenced_list.dirty = True
