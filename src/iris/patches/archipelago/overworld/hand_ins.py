"""Story hand-ins test the item, not the grant's flag (Iris-Dev#49). Linear Archipelago base patch only.

Four talk scripts take a story item from the party, but decide whether to on the flag the item's grant sets. In
Archipelago the grant is a location: its flag only says the spot was checked, while the item can come from anyone (RX
puts it in the inventory and sets no flag). So each gate ``15(flag-@target)`` becomes the item test ``10-C-03`` already
uses for the Crown, ``14(C2-item-01-20-@target-FF)``: sub-code ``C2`` is "the party holds ``01`` of the item" and
``20`` jumps when that is true (``30`` when it is false). The target and the item removal stay as they are.

The gate grows from 4 to 10 bytes, so the map's event container moves: ``structures.zone.move_all_zone_data`` must
have run. Open world drops these grants, so it doesn't need this.

Lexis's lab (``A2-B-2C``) builds the airship on GOT_ENGINE (98), which only the scene after the Gratze grant sets
(``A0-A-03``), not on the Engine (Iris-Dev#86). There the item gate is added in front of the flag gate, which stays: the
lab builds the airship from a held Engine or from the vanilla flag, and its ``25(C1-01)`` still takes the Engine.
Open world empties the lab's script.

Alunze's Crown line (``10-C-03``, Iris-Dev#26) shows a line and ``33(2D-00)`` while the party holds the Crown, with no
story-flag test: vanilla takes the Crown at the hand-in, but with ``scenario_items=no_removals`` it stays held and the
line came back forever. The script now starts with the hand-in's own ``15(28-@target)`` (RETURNED_CROWN_ALUNZE, set by
``10-B-59``, which starts with the same gate), jumping to its end once the Crown is handed in. Open world empties the
script.
"""

from dataclasses import dataclass

from iris.enums.event_scripts import EventClass
from iris.enums.flags import EventFlag
from iris.logger import iris
from iris.structures.event_script.containers import MapEvent
from iris.structures.event_script.instructions import Address, Instruction
from iris.structures.event_script.script import EventScript


BRANCH_ON_FLAG = 0x15
CONDITION = 0x14
HOLDS_ITEM = 0xC2
JUMP_IF_TRUE = 0x20
END_CONDITION = 0xFF


@dataclass(frozen=True)
class HandIn:
    map_index: int
    script_index: int
    """The talk script (``REFERENCED`` list) that removes the item."""
    flag: int
    """The grant's flag the vanilla gate tests."""
    item: int


ENGINE = 449
LEXIS_LAB = 0xA2
LEXIS_SCRIPT = 0x2C
"""Lexis's lab talk script: ``15(62-@75E)`` (GOT_ENGINE) jumps to the airship scene."""
ALUNZE = 0x10
CROWN_LINE = 0x03
"""Alunze's NPC script ``10-C-03``: ``14(C2-459-01-30-@1D-FF)``, a line, ``33(2D-00)``, ``00`` at @1D."""
CROWN = 459
END = 0x00


HAND_INS = (
    HandIn(0x10, 0x59, EventFlag.PICKED_UP_CROWN, 459),  # King of Alunze, Crown
    HandIn(0x26, 0x55, EventFlag.RECEIVED_RUBY_APPLE, 460),  # Ruby apple
    HandIn(0x89, 0x25, EventFlag.TALKED_JAFFY_RUBY_ICON, 452),  # Queen, Glass angel
    HandIn(0x7B, 0x24, EventFlag.RECEIVED_PRETTY_FLOWER, 451),  # Pretty flower
)


def _script(map_index: int, script_index: int, event_class: EventClass = EventClass.REFERENCED) -> EventScript:
    map_event = MapEvent.from_index(map_index)
    map_event.read()
    return next(
        script
        for event_list in map_event.event_lists
        if event_list.event_class is event_class
        for script in event_list.events
        if script.index == script_index
    )


def _gate(script: EventScript, flag: int) -> int:
    """Position of the ``15(flag-@target)`` that gates the hand-in."""
    for position, instruction in enumerate(script.instructions):
        if instruction.opcode == BRANCH_ON_FLAG and instruction.operands[0] == flag:
            return position
    msg = f"Script {script.index:#x} has no gate on flag {flag}."
    raise ValueError(msg)


def gate_hand_ins_on_items() -> None:
    """Make each hand-in in :data:`HAND_INS` jump to its reward when the party holds the item."""
    for hand_in in HAND_INS:
        script = _script(hand_in.map_index, hand_in.script_index)
        position = _gate(script, hand_in.flag)
        gate = script.instructions[position]
        target = gate.operands[1]
        if not isinstance(target, Address):
            msg = f"Gate {gate} has no jump target."
            raise TypeError(msg)
        script.instructions[position] = Instruction(
            gate.line,
            CONDITION,
            [HOLDS_ITEM, hand_in.item, 1, JUMP_IF_TRUE, Address(target.offset), END_CONDITION],
        )
        script.dirty = True
        MapEvent.from_index(hand_in.map_index).write()
        iris.debug(f"Hand-in {hand_in.map_index:02X}-{hand_in.script_index:02X} tests item {hand_in.item}.")


def gate_airship_on_engine() -> None:
    """Make Lexis's lab jump to its airship scene when the party holds the Engine, as well as on GOT_ENGINE."""
    script = _script(LEXIS_LAB, LEXIS_SCRIPT)
    position = _gate(script, EventFlag.GOT_ENGINE)
    gate = script.instructions[position]
    target = gate.operands[1]
    if not isinstance(target, Address):
        msg = f"Gate {gate} has no jump target."
        raise TypeError(msg)
    script.instructions.insert(
        position,
        Instruction(
            gate.line - 1,  # between the GOT_AIRSHIP and GOT_ENGINE gates; no jump lands inside a 4-byte gate
            CONDITION,
            [HOLDS_ITEM, ENGINE, 1, JUMP_IF_TRUE, Address(target.offset), END_CONDITION],
        ),
    )
    script.dirty = True
    MapEvent.from_index(LEXIS_LAB).write()
    iris.debug(f"Lexis's lab {LEXIS_LAB:02X}-{LEXIS_SCRIPT:02X} builds the airship from a held Engine.")


def stop_crown_line_after_hand_in() -> None:
    """Make Alunze's Crown line (``10-C-03``) jump to its end once the Crown is handed in (RETURNED_CROWN_ALUNZE)."""
    script = _script(ALUNZE, CROWN_LINE, EventClass.NPC)
    first = script.instructions[0]
    end = script.instructions[-1]
    if first.opcode != CONDITION or first.operands[:2] != [HOLDS_ITEM, CROWN] or end.opcode != END:
        msg = f"Alunze's Crown line isn't the vanilla 10-C-03: {script.instructions}"
        raise ValueError(msg)
    script.instructions.insert(
        0,
        Instruction(first.line - 1, BRANCH_ON_FLAG, [EventFlag.RETURNED_CROWN_ALUNZE, Address(end.line)]),
    )
    script.dirty = True
    MapEvent.from_index(ALUNZE).write()
    iris.debug(f"Alunze's Crown line {ALUNZE:02X}-{CROWN_LINE:02X} stops after the hand-in.")
