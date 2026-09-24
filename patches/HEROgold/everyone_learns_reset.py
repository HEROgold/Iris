"""Let every character learn Reset, and teach it to the whole party in the tutorial cave.

Vanilla only lets Maxim learn Reset: the spell record's "who can learn" byte is ``0x01``, and the Secret Skills
Cave (map 5) teaches it with ``23(00-26)``, "character 0 learns spell 0x26". That event writes into Maxim's stat
block whether or not he's in the party, so a party that removed Maxim through the Elcid toggle never gets Reset.

This patch sets the learn byte to all seven characters and, after each ``23(00-26)``, adds
``6A(party flag -> skip) ; 23(XX-26)`` for every other character. Only characters in the party at that moment
learn it, so no stat block of a character who hasn't joined yet is touched. The grown scripts make
``MapEvent.write`` relocate the map's event container.
"""

from helpers.files import write_file
from logger import iris
from scripting.l2basm.records import spell_records
from structures.character import PlayableCharacter
from structures.event_script.containers import MapEvent
from structures.event_script.instructions import Address, Instruction
from structures.event_script.script import EventScript


RESET = 0x26
ALL_CHARACTERS = 0x7F  # bits 0-6: Maxim, Selan, Guy, Artea, Tia, Dekar, Lexis
TUTORIAL_MAP = 0x05  # Secret Skills Cave
_SPELL_CHARACTERS = 10  # record offset of the spell's "who can learn" byte
_LEARN_SPELL = 0x23
_IF_FLAG_CLEAR = 0x6A  # 6A(flag -> address): jump when the event flag is clear
_OTHER_CHARACTERS = range(1, 7)
_SHIFT = 0x20  # room for the inserted lines: every later line number moves up by this much


def _shift(operand: object, after: int) -> object:
    if isinstance(operand, Address) and operand.offset > after:
        return Address(operand.offset + _SHIFT)
    if isinstance(operand, list):
        return [_shift(item, after) for item in operand]
    return operand


def _teach_the_party(script: EventScript) -> bool:
    """Expand each ``23(00-26)`` in ``script`` into grants for every party member. True if it changed."""
    grants = [
        i for i, ins in enumerate(script.instructions) if ins.opcode == _LEARN_SPELL and ins.operands == [0, RESET]
    ]
    for position in reversed(grants):
        grant = script.instructions[position]
        after = grant.line
        for ins in script.instructions:
            ins.operands = [_shift(op, after) for op in ins.operands]  # type: ignore[misc]
        tail = script.instructions[position + 1 :]
        for ins in tail:
            ins.line += _SHIFT
        line = after + 1
        added: list[Instruction] = []
        for index in _OTHER_CHARACTERS:
            flag = PlayableCharacter.from_index(index).party_flag
            skip = line + 2 if index != _OTHER_CHARACTERS[-1] else (tail[0].line if tail else line + 2)
            added.append(Instruction(line, _IF_FLAG_CLEAR, [flag, Address(skip)]))
            added.append(Instruction(line + 1, _LEARN_SPELL, [index, RESET]))
            line += 2
        script.instructions = [*script.instructions[: position + 1], *added, *tail]
    if grants:
        script.dirty = True
    return bool(grants)


def everyone_learns_reset() -> None:
    iris.info("Reset: learnable by every character; the tutorial teaches it to the whole party.")
    record = spell_records(write_file)[RESET]  # type: ignore[arg-type]
    write_file.seek(record.start + _SPELL_CHARACTERS)
    write_file.write(bytes([ALL_CHARACTERS]))

    map_event = MapEvent.from_index(TUTORIAL_MAP)
    changed = [script for event_list in map_event.event_lists for script in event_list.events if _teach_the_party(script)]
    if changed:
        map_event.write()
    iris.info(f"  {len(changed)} Reset grant script(s) on map {TUTORIAL_MAP:#04x} now teach the whole party.")
