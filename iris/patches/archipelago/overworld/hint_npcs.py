"""NPCs whose talk script the Archipelago world can overwrite with a hint (Iris-Dev#33).

A candidate's script is nothing but text boxes (``08`` text, each ending in END MESSAGE, the last in END EVENT), so
replacing it changes nothing but what the NPC says. The apworld writes ``1A(flag)`` and its own text boxes over it
with tokens; the client reads the flag as "talked to" and unlocks the hint.

The apworld can't move scripts (Iris isn't shipped), so the base patch makes the room: :func:`make_hint_slots` grows
every candidate to at least :data:`HINT_SLOT_SIZE` bytes, which moves its map's event container into the space
ZoneData left in banks $91-$94 (``structures.zone.move_all_zone_data``). The data export reads the slots from the
built ROM (:func:`hint_slots`).

Excluded:

- scripts another script jumps into (``EventScript.jumped_into``);
- scripts another patch of the build changes (the Elcid party toggle, ...);
- maps the AP world leaves out (the Ancient Cave).

Text other scripts copy with a ``<REPEAT>`` no longer matters: a moved container's old bytes stay where they were.
"""

from dataclasses import dataclass, replace

from iris.enums.event_scripts import EventClass
from iris.helpers.files import on_new_session, read_file
from iris.structures.event_script.compiler import compile_script
from iris.structures.event_script.containers import MapEvent, reset_map_events
from iris.structures.event_script.dump import _signature
from iris.structures.event_script.instructions import Instruction
from iris.structures.event_script.script import EventScript
from iris.tables import MapEventObject


TALK_SCRIPT_START = 0x50
"""Talk scripts are the REFERENCED scripts 0x50 and up (index = NPC slot)."""
MIN_SIZE = 40
"""Shorter scripts are left out, to keep the number of moved containers down."""
HINT_SLOT_SIZE = 160
"""Bytes every hint slot holds at least: the longest hint wording, "Your <item> is in <owner>'s world (<game>):
<location>.", in boxes of three 24-character lines."""
SLOT_FILL = 0x42
"""Pads a slot after its END EVENT: an END itself, never run, and not a blank byte asar's ``freecode`` could take."""
EXCLUDED_MAPS = frozenset((0xEF, 0xF0, 0xF1))
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
    raw: bytes
    """The script's bytes when it was picked, to tell whether another patch changed it since."""


def _text_end(raw: bytes, start: int) -> int:
    """Walk one text run from ``start``; return the offset after its terminator."""
    i = start
    while i < len(raw):
        code = raw[i]
        i += 1
        if code in (_END_EVENT, _END_MESSAGE, _CHOICE):
            return i
        if code == _REPEAT:
            i += 2
        elif code in _ONE_BYTE_CODES:
            i += 1
    return i


def _plain_text(raw: bytes) -> bool:
    """Only ``08`` text boxes, the last ending the event, no choices."""
    i = 0
    while i < len(raw):
        if raw[i] != _TEXT_BOX:
            return False
        i = _text_end(raw, i + 1)
        if raw[i - 1] == _CHOICE:
            return False
        if raw[i - 1] == _END_EVENT:
            return True
    return False


def hint_npc_candidates() -> list[HintNpc]:
    """Every talk script of the active session that a hint can replace. Call it before other patches change scripts."""
    out = []
    for index in range(MapEventObject.count):
        if index in EXCLUDED_MAPS:
            continue
        map_event = MapEvent.from_index(index)
        map_event.read()
        for event_list in map_event.event_lists:
            out.extend(
                HintNpc(index, _signature(index, script), script.pointer, len(script.raw), script.raw)
                for script in event_list.events
                if script.event_class == EventClass.REFERENCED
                and script.index >= TALK_SCRIPT_START
                and not script.jumped_into
                and len(script.raw) >= MIN_SIZE
                and _plain_text(script.raw)
            )
    return out


_slots: list[HintNpc] = []


@on_new_session
def _reset_slots() -> None:
    _slots.clear()


def hint_slots() -> list[HintNpc]:
    """The slots :func:`make_hint_slots` made in the active session, for the data export."""
    return list(_slots)


def _unchanged(candidate: HintNpc) -> bool:
    read_file.seek(candidate.pointer)
    return read_file.read(len(candidate.raw)) == candidate.raw


def _script(map_event: MapEvent, signature: str) -> EventScript:
    return next(
        script
        for event_list in map_event.event_lists
        for script in event_list.events
        if _signature(map_event.index, script) == signature
    )


def _pad(script: EventScript) -> None:
    """Append END instructions until the script, compiled as a move compiles it, fills HINT_SLOT_SIZE bytes."""
    missing = HINT_SLOT_SIZE - len(compile_script(script, ignore_pointers=True, compress=True))
    line = script.instructions[-1].line + 0x100
    script.instructions.extend(Instruction(line + i, SLOT_FILL, []) for i in range(missing))
    script.dirty = missing > 0


def make_hint_slots(candidates: list[HintNpc]) -> list[HintNpc]:
    """Grow every candidate no other patch changed to a HINT_SLOT_SIZE slot, moving its map's container as needed.

    Needs room in banks $80-$BF: call ``structures.zone.move_all_zone_data`` first. Maps are parsed again from the
    image, so whatever other patches wrote is kept when a container moves.
    """
    reset_map_events()
    by_map: dict[int, list[HintNpc]] = {}
    for candidate in filter(_unchanged, candidates):
        by_map.setdefault(candidate.map_index, []).append(candidate)
    for map_index, npcs in by_map.items():
        map_event = MapEvent.from_index(map_index)
        map_event.read()
        for npc in npcs:
            _pad(_script(map_event, npc.signature))
        map_event.write()
        for npc in npcs:
            script = _script(map_event, npc.signature)
            _slots.append(replace(npc, pointer=script.pointer, size=len(script.raw), raw=script.raw))
    return hint_slots()


HINT_FLAGS = tuple(range(227, 240))
"""One event flag per hint NPC, set when you talk to it. 220-239 is the one block no vanilla script uses; 220-226 are
Iris's FOUND_* flags (``enums.flags.EventFlag``), so 227-239 are left: at most 13 hint NPCs."""
