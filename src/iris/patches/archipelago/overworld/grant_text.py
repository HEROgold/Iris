"""A grant's "Gets ..." message names the item placed there (Iris-Dev#52). Linear Archipelago base patch only.

Each AP grant with a ``9E: <POSITION 06>Gets the ....`` message gets a fixed-size text slot that holds the vanilla
message. A seed whose grant holds another item writes "Gets <name>." over the slot as a token (``lufia2ow/grant_text.py``),
so no container moves per seed.

**Why not a text code.** The dialogue engine dispatches the control codes 00-0F through the jump table at $80:CA14.
None prints an item name from a variable: ``02`` is a BRK, ``07 xx`` draws glyph 0x300 + xx, and ``09`` ($MAXIM$)
switches the text pointer to the name at $00:0BAD and back. Chests print their item through the system-message
routine ($8E:C1EB -> $80:93FE), not through script text.

**Padding.** ``04 80`` (``<PAUSE 80>``) waits one frame ($80:9E0B) and the window-width pass ($80:C652) gives it no
width, so it pads a slot without showing. An odd byte left over is a trailing space.

**The slot stays put.** The text holds no run of 4 or more plain characters (a ``<PAUSE 80>`` breaks longer runs), so
neither compressing the script again (``codec.RepeatWindow``) nor another script's ``<REPEAT>`` can copy or shorten it.
Each map's container is moved (:meth:`MapEvent.reserve`): vanilla text that copied bytes from the old message keeps
reading the old bytes, which stay.

Pickup lines that name the vanilla item are made neutral (:data:`NEUTRAL_LINES`).

Grants with no "Gets" message (the Ear jewel ``26-A-01``, Dual Blade in ``E4-C-01``) are left as they are; ``05-*`` and
``10-*`` grant nothing, so they aren't locations. Open world keeps none of these grants.
"""

from dataclasses import dataclass

from iris.logger import iris
from iris.structures.event_script.codec import (
    REPEAT_COPYABLE,
    REPEAT_MIN_LENGTH,
    TEXT_PARAMETERS,
    decode_text,
    encode_text,
    render_text,
)
from iris.structures.event_script.containers import MapEvent
from iris.structures.event_script.dump import _signature
from iris.structures.event_script.instructions import Instruction, TextChunk
from iris.structures.event_script.script import EventScript
from iris.tables import ItemNameObject


TEXT_WINDOW = 0x9E
POSITION = "POSITION"
END_MESSAGE = 0x01
GETS = "Gets"
PREFIX = b"Gets "
SUFFIX = b"."
PAUSE = b"\x04\x80"
"""``<PAUSE 80>``: one frame, no width."""
PAUSE_TAG = "<PAUSE 80>"
NAME_SIZE = ItemNameObject.name_text
MESSAGE_SIZE = len(PREFIX) + NAME_SIZE + len(SUFFIX)
"""The longest message a seed writes: "Gets <12-character name>."."""
MAX_RUN = REPEAT_MIN_LENGTH - 1
"""Plain characters in a row the slot may hold: a ``<REPEAT>`` copies 4 or more."""


@dataclass(frozen=True)
class GrantText:
    map_index: int
    signature: str
    item: int
    """The grant's vanilla item; the slot belongs to the grant of this item."""


GRANT_TEXTS = (
    GrantText(0x07, "07-C-01", 429),  # Key to the door
    GrantText(0x14, "14-C-03", 459),  # Crown
    GrantText(0x26, "26-B-18", 452),  # Ruby icon
    GrantText(0x2A, "2A-B-18", 460),  # Ruby apple
    GrantText(0x3D, "3D-C-01", 108),  # Gades' sword
    GrantText(0x3F, "3F-B-1B", 43),  # Dragon egg
    GrantText(0x7E, "7E-C-01", 451),  # Pretty flower
    GrantText(0x8B, "8B-B-25", 453),  # VIP card
    GrantText(0xBF, "BF-B-2D", 448),  # Jade of mermaids
    GrantText(0xD6, "D6-C-02", 449),  # Engine
    GrantText(0xDC, "DC-C-01", 226),  # Divine armor
    GrantText(0xE0, "E0-C-01", 322),  # Divine helmet
    GrantText(0xE4, "E4-C-01", 270),  # Divine shield
)


@dataclass(frozen=True)
class NeutralLine:
    map_index: int
    signature: str
    old: str
    """Part of the line as the dump renders it."""
    new: str


NEUTRAL_LINES = (
    NeutralLine(0x14, "14-C-03", "look! The crown!", "look! Over there!"),
    NeutralLine(0x2A, "2A-B-18", "take this apple.", "take this."),
    NeutralLine(0x8B, "8B-B-25", "with this VIP card.", "with this."),
    NeutralLine(0x8B, "8B-B-25", "Island with this card.", "Island with a VIP card."),
    NeutralLine(0xDC, "DC-C-01", "The Divine Armor\nis inside there.", "What you seek\nis inside there."),
)


@dataclass(frozen=True)
class TextSlot:
    map_index: int
    signature: str
    item: int
    offset: int
    """Headerless offset of the message text, after ``9E`` and its position byte."""
    size: int
    """Bytes the text may take; its END MESSAGE follows."""


def _script(map_index: int, signature: str) -> EventScript:
    map_event = MapEvent.from_index(map_index)
    map_event.read()
    return next(
        script
        for event_list in map_event.event_lists
        for script in event_list.events
        if _signature(map_index, script) == signature
    )


def _gets_message(script: EventScript) -> Instruction:
    """The script's one ``9E`` "Gets ..." message."""
    found = [
        instruction
        for instruction in script.instructions
        if instruction.opcode == TEXT_WINDOW and _body(instruction).startswith(GETS)
    ]
    if len(found) != 1:
        msg = f"Script {script.index:#x} has {len(found)} 'Gets' messages, not one."
        raise ValueError(msg)
    return found[0]


def _chunks(instruction: Instruction) -> list[TextChunk]:
    chunks = instruction.operands[0]
    if not isinstance(chunks, list):
        msg = f"{instruction} has no text."
        raise TypeError(msg)
    return chunks


def _body(instruction: Instruction) -> str:
    """The message's text, without its position, its END MESSAGE and the slot's pauses."""
    chunks = _chunks(instruction)
    return render_text([chunk for chunk in chunks if chunk.tag not in {POSITION, END_MESSAGE}]).replace(PAUSE_TAG, "")


def _broken_runs(data: bytes) -> bytes:
    """``data`` with a ``<PAUSE 80>`` wherever it would hold more than :data:`MAX_RUN` plain characters in a row."""
    out = bytearray()
    run = 0
    position = 0
    while position < len(data):
        byte = data[position]
        if byte in TEXT_PARAMETERS:
            out += data[position : position + 1 + TEXT_PARAMETERS[byte]]
            position += 1 + TEXT_PARAMETERS[byte]
            run = 0
            continue
        if byte in REPEAT_COPYABLE:
            if run == MAX_RUN:
                out += PAUSE
                run = 0
            run += 1
        else:
            run = 0
        out.append(byte)
        position += 1
    return bytes(out)


def base_text(vanilla: str) -> bytes:
    """The slot as the base patch writes it: the vanilla message, its runs broken, padded with pauses.

    The slot fits :data:`MESSAGE_SIZE` and has the vanilla text's parity, so the vanilla text needs no space.
    """
    text = _broken_runs(encode_text(vanilla))
    size = max(len(text), MESSAGE_SIZE)
    size += (size - len(text)) % 2
    return text + PAUSE * ((size - len(text)) // 2)


def _neutral(script: EventScript, line: NeutralLine) -> None:
    hits = [
        (position, instruction)
        for position, instruction in enumerate(script.instructions)
        if any(isinstance(operand, list) for operand in instruction.operands) and line.old in render_text(_chunks(instruction))
    ]
    if len(hits) != 1:
        msg = f"{line.signature}: {len(hits)} lines hold {line.old!r}, not one."
        raise ValueError(msg)
    position, instruction = hits[0]
    text = render_text(_chunks(instruction)).replace(line.old, line.new)
    chunks, _ = decode_text(instruction.opcode, encode_text(text), b"", b"")
    script.instructions[position] = Instruction(instruction.line, instruction.opcode, [chunks])


def name_placed_items() -> None:
    """Give every grant in :data:`GRANT_TEXTS` a fixed-size message slot and make the lines in :data:`NEUTRAL_LINES`
    neutral, moving each map's event container. Needs ``structures.zone.move_all_zone_data`` first."""
    maps = sorted({grant.map_index for grant in GRANT_TEXTS})
    for map_index in maps:
        for grant in (grant for grant in GRANT_TEXTS if grant.map_index == map_index):
            script = _script(map_index, grant.signature)
            message = _gets_message(script)
            position = script.instructions.index(message)
            chunks = _chunks(message)
            slot = base_text(_body(message))
            new, _ = decode_text(TEXT_WINDOW, chunks[0].data + slot + bytes([END_MESSAGE]), b"", b"")
            script.instructions[position] = Instruction(message.line, TEXT_WINDOW, [new])
            script.dirty = True
            iris.debug(f"Grant {grant.signature}: {len(slot)}-byte message slot.")
        for line in (line for line in NEUTRAL_LINES if line.map_index == map_index):
            script = _script(map_index, line.signature)
            _neutral(script, line)
            script.dirty = True
        MapEvent.from_index(map_index).reserve()


def text_slots() -> list[TextSlot]:
    """Where each grant's message slot is in the active session (after :func:`name_placed_items`)."""
    out = []
    for grant in GRANT_TEXTS:
        script = _script(grant.map_index, grant.signature)
        message = _gets_message(script)
        slot = base_text(_body(message))
        offset = script.pointer + message.line + 2  # 9E, position
        if script.raw[message.line + 2 : message.line + 2 + len(slot) + 1] != slot + bytes([END_MESSAGE]):
            msg = f"Grant {grant.signature}: its message slot changed after the base patch made it."
            raise ValueError(msg)
        out.append(TextSlot(grant.map_index, grant.signature, grant.item, offset, len(slot)))
    return out
