"""Three script grants set a flag the Archipelago client reads (Iris-Dev#22). Every Archipelago base patch.

A grant is an AP location when its script sets an event flag (``tools/export_ap_data._grants``), and the client
reports the location once that flag is set. In vanilla three grants set none: the Ear jewel, the Merix Dragon egg and
the Engine. Each gets a ``1A(flag)`` with a new flag (``EventFlag.RECEIVED_*``) right after its ``20``/``21`` grant.

The script grows by 2 bytes, so the map's event container may move: ``structures.zone.move_all_zone_data`` must
have run. Open world replaces some of these scripts; a script that no longer grants its item is left alone.
"""

from dataclasses import dataclass

from iris.enums.flags import EventFlag
from iris.logger import iris
from iris.structures.event_script.containers import MapEvent
from iris.structures.event_script.dump import _signature
from iris.structures.event_script.instructions import Instruction
from iris.structures.event_script.script import EventScript


SET_FLAG = 0x1A
GRANT_OPS = {0x20: 0x000, 0x21: 0x100}
"""Get-item opcode -> the item-number base its 1-byte operand adds to."""


@dataclass(frozen=True)
class FlaggedGrant:
    map_index: int
    signature: str
    """The grant script, as ``tools/export_ap_data`` names it (``MM-L-II``)."""
    item: int
    flag: EventFlag


FLAGGED_GRANTS = (
    FlaggedGrant(0x26, "26-A-01", 323, EventFlag.RECEIVED_EAR_JEWEL),
    FlaggedGrant(0x3F, "3F-B-1B", 43, EventFlag.RECEIVED_DRAGON_EGG_MERIX),
    FlaggedGrant(0xD6, "D6-C-02", 449, EventFlag.RECEIVED_ENGINE),
)


def _script(grant: FlaggedGrant) -> EventScript | None:
    map_event = MapEvent.from_index(grant.map_index)
    map_event.read()
    return next(
        (
            script
            for event_list in map_event.event_lists
            for script in event_list.events
            if _signature(grant.map_index, script) == grant.signature
        ),
        None,
    )


def _grant_position(script: EventScript, item: int) -> int | None:
    """Position of the ``20``/``21`` instruction that grants ``item``."""
    for position, instruction in enumerate(script.instructions):
        operand = instruction.operands[0] if instruction.opcode in GRANT_OPS else None
        if isinstance(operand, int) and GRANT_OPS[instruction.opcode] + operand == item:
            return position
    return None


def set_flags_on_grants() -> list[FlaggedGrant]:
    """Make each grant in :data:`FLAGGED_GRANTS` that still grants its item set its flag; return the ones changed."""
    changed = []
    for grant in FLAGGED_GRANTS:
        script = _script(grant)
        position = None if script is None else _grant_position(script, grant.item)
        if script is None or position is None:
            iris.debug(f"{grant.signature} doesn't grant item {grant.item}; no flag to set.")
            continue
        line = script.instructions[position].line + 1  # inside the 3-byte grant, so no jump targets it
        script.instructions.insert(position + 1, Instruction(line, SET_FLAG, [int(grant.flag)]))
        script.dirty = True
        MapEvent.from_index(grant.map_index).write()
        changed.append(grant)
        iris.debug(f"Grant {grant.signature} (item {grant.item}) sets flag {int(grant.flag)}.")
    return changed
