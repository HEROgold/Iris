"""NPCs whose talk script the Archipelago world can overwrite with a hint (Iris-Dev#33).

A candidate's script is nothing but text boxes (``08`` text, each ending in END MESSAGE, the last in END EVENT), so
replacing it changes nothing but what the NPC says. The apworld writes ``1A(flag)`` and its own text boxes over it, in
place, with tokens; the client reads the flag as "talked to" and unlocks the hint.

Excluded:

- scripts another script jumps into (``EventScript.jumped_into``);
- scripts with bytes some text copies with a ``<REPEAT>`` back-reference: those bytes must stay;
- scripts the AP base patch changes (the Elcid party toggle, ...), found by comparing with the patched ROM;
- maps the AP world leaves out (the Ancient Cave).
"""

from dataclasses import dataclass

from iris.enums.event_scripts import EventClass
from iris.helpers.files import read_file
from iris.structures.event_script.containers import MapEvent
from iris.structures.event_script.dump import _signature
from iris.structures.event_script.opcodes import ENTER_TEXT_MODE
from iris.structures.event_script.script import EventScript
from iris.tables import MapEventObject


TALK_SCRIPT_START = 0x50
"""Talk scripts are the REFERENCED scripts 0x50 and up (index = NPC slot)."""
MIN_SIZE = 40
"""Shorter scripts can't hold a useful hint."""
EXCLUDED_MAPS = frozenset((0xEF, 0xF0, 0xF1))
_TEXT_PREFIX = {0x13: 1, 0x6D: 2, 0x6E: 2, 0x9E: 1}
_ONE_BYTE_CODES = {0x04, 0x05, 0x06}
_REPEAT = 0x0A
_END_EVENT, _END_MESSAGE, _CHOICE = 0x00, 0x01, 0x0B
_TEXT_BOX = 0x08


@dataclass(frozen=True)
class HintNpc:
    map_index: int
    signature: str
    pointer: int
    """Headerless offset of the script."""
    size: int
    """Bytes the script may take: its slot."""


def _text_end(raw: bytes, start: int, repeats: list[tuple[int, int, int]], pointer: int) -> int:
    """Walk one text run from ``start``; return the offset after its terminator. Collects back-reference sources."""
    i = start
    while i < len(raw):
        code = raw[i]
        i += 1
        if code in (_END_EVENT, _END_MESSAGE, _CHOICE):
            return i
        if code == _REPEAT:
            value = int.from_bytes(raw[i : i + 2], "little")
            i += 2
            source = pointer + i - ((value & 0x0FFF) + 2)
            repeats.append((source, source + (value >> 12) + 2, pointer))
        elif code in _ONE_BYTE_CODES:
            i += 1
    return i


def _repeat_sources(script: EventScript, repeats: list[tuple[int, int, int]]) -> None:
    for instruction in script.instructions:
        if instruction.opcode in ENTER_TEXT_MODE:
            start = instruction.line + 1 + _TEXT_PREFIX.get(instruction.opcode, 0)
            _text_end(script.raw, start, repeats, script.pointer)


def _plain_text(raw: bytes) -> bool:
    """Only ``08`` text boxes, the last ending the event, no choices."""
    i = 0
    ignored: list[tuple[int, int, int]] = []
    while i < len(raw):
        if raw[i] != _TEXT_BOX:
            return False
        i = _text_end(raw, i + 1, ignored, 0)
        if raw[i - 1] == _CHOICE:
            return False
        if raw[i - 1] == _END_EVENT:
            return True
    return False


def hint_npc_candidates(patched: bytes) -> list[HintNpc]:
    """Every talk script of the active (vanilla) session that a hint can replace, given the AP base patch's output."""
    scripts: list[tuple[int, EventScript]] = []
    repeats: list[tuple[int, int, int]] = []
    """(source start, source end, script that copies): bytes some text copies from."""
    for index in range(MapEventObject.count):
        map_event = MapEvent.from_index(index)
        map_event.read()
        for event_list in map_event.event_lists:
            for script in event_list.events:
                _repeat_sources(script, repeats)
                scripts.append((index, script))
    out = []
    for map_index, script in scripts:
        if (
            map_index in EXCLUDED_MAPS
            or script.event_class != EventClass.REFERENCED
            or script.index < TALK_SCRIPT_START
            or script.jumped_into
            or len(script.raw) < MIN_SIZE
            or not _plain_text(script.raw)
        ):
            continue
        start, end = script.pointer, script.pointer + len(script.raw)
        if any(source < end and start < stop and owner != start for source, stop, owner in repeats):
            continue
        read_file.seek(start)
        if patched[start:end] != read_file.read(end - start):
            continue
        out.append(HintNpc(map_index, _signature(map_index, script), start, len(script.raw)))
    return out


HINT_FLAGS = tuple(range(227, 240))
"""One event flag per hint NPC, set when you talk to it. 220-239 is the one block no vanilla script uses; 220-226 are
Iris's FOUND_* flags (``enums.flags.EventFlag``), so 227-239 are left: at most 13 hint NPCs."""
