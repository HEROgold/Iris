"""The round-trippable text dump format and its importer.

A dump renders the structured tree keyed by ``MAP-CLASS-INDEX`` signatures; the importer parses that
text back into :class:`Instruction`s and replaces the targeted script's instruction list. Line
offsets and ``$addr`` values are *labels only* -- never trusted as byte positions; the compiler
recomputes them.
"""

import logging
import re

from enums.event_scripts import EventClass
from logger import iris
from structures.event_script.codec import decode_text, encode_text, render_text
from structures.event_script.containers import MapEvent
from structures.event_script.instructions import Address, Instruction
from structures.event_script.opcodes import (
    ADDR,
    POINTERS,
    TEXT,
    VARIABLE,
    op_codes,
    operand_shape,
)
from structures.event_script.script import EventScript
from tables import MapEventObject


log = logging.getLogger(f"{iris.name}.Dump")

CLASS_LETTERS = "XABCDEF"
_LETTER_TO_CLASS = {letter: EventClass(value) for value, letter in enumerate(CLASS_LETTERS)}
_LINE_MATCHER = re.compile(r"^\s*([0-9A-Fa-f]+)\.\s")
_EVENT_MATCHER = re.compile(r"^\s*EVENT\s+(\S+)")


def class_letter(event_class: EventClass) -> str:
    """Signature letter for an event class (the NPC-load script dumps as ``X``)."""
    if event_class is EventClass.NPC_SCRIPT:
        return "X"
    return CLASS_LETTERS[event_class.value]


def _signature(map_index: int, script: EventScript) -> str:
    letter = class_letter(script.event_class)
    index = "XX" if script.index < 0 else f"{script.index:02X}"
    return f"{map_index:02X}-{letter}-{index}"


def _render_operands(instruction: Instruction) -> str:
    shape = operand_shape(instruction.opcode)
    parts: list[str] = []
    operand_index = 0
    for token in shape:
        if token == POINTERS:
            count = instruction.operands[operand_index]
            parts.append(f"{int(count):02X}")
            for j in range(int(count)):
                parts.append(repr(instruction.operands[operand_index + 1 + j]))
            operand_index += 1 + int(count)
        elif token == VARIABLE:
            for operand in instruction.operands[operand_index:]:
                parts.append(repr(operand) if isinstance(operand, Address) else f"{int(operand):02X}")
            operand_index = len(instruction.operands)
        elif token == ADDR:
            parts.append(repr(instruction.operands[operand_index]))
            operand_index += 1
        else:
            width = int(token) * 2
            value = instruction.operands[operand_index]
            parts.append(f"{int(value):0{width}X}")
            operand_index += 1
    return "-".join(parts)


def dump_instruction(instruction: Instruction) -> str:
    """Render one instruction line (without the trailing comment)."""
    shape = operand_shape(instruction.opcode)
    if shape == (TEXT,):
        chunks = instruction.operands[0]
        text = render_text(chunks) if isinstance(chunks, list) else ""
        body = f"{instruction.opcode:02X}: {text}"
    else:
        body = f"{instruction.opcode:02X}({_render_operands(instruction)})"
    comment = op_codes.get(instruction.opcode, {}).get("comment", "")
    line = f"{instruction.line:04X}. {body}"
    if comment:
        line = f"{line}  # {comment.strip()}"
    return line


def dump_script(map_index: int, script: EventScript) -> str:
    lines = [f"EVENT {_signature(map_index, script)}  # ${script.base_pointer:x}:{script.pointer:x}"]
    lines.extend(f"  {dump_instruction(instruction)}" for instruction in script.instructions)
    return "\n".join(lines)


def dump_map(map_event: MapEvent) -> str:
    """Dump every script of ``map_event`` to the round-trippable text format."""
    map_event.read()
    name = map_event.clean_map_name.decode("ascii", errors="replace")
    blocks = [f"# MAP {map_event.index:02X}-{map_event.pointer:05x} ({name})"]
    for event_list in map_event.event_lists:
        for script in event_list.events:
            blocks.append(dump_script(map_event.index, script))
    return "\n\n".join(blocks)


def dump_all() -> str:
    """Concatenate :func:`dump_map` over every map."""
    return "\n\n".join(dump_map(MapEvent.from_index(i)) for i in range(MapEventObject.count))


def _resolve_script(signature: str) -> EventScript:
    map_index_str, letter, index_str = signature.split("-")
    map_event = MapEvent.from_index(int(map_index_str, 16))
    event_class = _LETTER_TO_CLASS[letter]
    for event_list in map_event.event_lists:
        if letter == "X" and event_list.event_class is EventClass.NPC_SCRIPT and index_str == "XX":
            return event_list.events[0]
        if event_list.event_class is event_class:
            for script in event_list.events:
                if script.index == int(index_str, 16):
                    return script
    msg = f"No script for signature {signature}."
    raise ValueError(msg)


def _parse_instruction_line(line: int, opcode: int, body: str, *, is_text: bool) -> Instruction:
    if is_text:
        chunks, _ = decode_text(opcode, encode_text(body, compress=opcode not in {0x6D, 0x6E}), b"", b"")
        return Instruction(line, opcode, [chunks])
    operands: list[object] = []
    for token in filter(None, body.split("-")):
        if token.startswith("@"):
            # Forward and backward local jumps are both legal; the compiler validates/relocates the
            # target against the script's real line numbers (see compiler._snap).
            operands.append(Address(int(token[1:], 16)))
        else:
            operands.append(int(token, 16))
    return Instruction(line, opcode, operands)  # type: ignore[arg-type]


def parse_dump(text: str) -> None:
    """Parse dump text and replace the ``instructions`` of every referenced script (marks dirty).

    A physical line that does not start with ``NNNN.`` is a *continuation* of the previous
    instruction -- it reassembles multi-line dialogue whose embedded newlines came from ``0x03``.
    """
    current: EventScript | None = None
    pending: list[Instruction] = []
    last_line = -1
    buffer: tuple[int, int, str, bool] | None = None

    def commit() -> None:
        nonlocal buffer
        if buffer is not None:
            line_number, opcode, body, is_text = buffer
            pending.append(_parse_instruction_line(line_number, opcode, body, is_text=is_text))
            buffer = None

    def flush() -> None:
        commit()
        if current is not None:
            current.instructions = list(pending)
            current.dirty = True

    for raw_line in text.splitlines():
        event_match = _EVENT_MATCHER.match(raw_line)
        if event_match:
            flush()
            current = _resolve_script(event_match.group(1))
            pending = []
            last_line = -1
            continue
        line = raw_line.split("#", 1)[0].rstrip()
        if current is None:
            continue
        match = _LINE_MATCHER.match(line)
        if not match:
            if buffer is not None and line:  # continuation of multi-line dialogue
                line_number, opcode, body, is_text = buffer
                buffer = (line_number, opcode, f"{body}\n{line.strip()}", is_text)
            continue
        commit()
        line_number = int(match.group(1), 16)
        if line_number <= last_line:
            msg = "Lines out of order"
            raise ValueError(msg)
        last_line = line_number
        rest = line[match.end():]
        is_text = ":" in rest and (":" in rest.split("(", 1)[0])
        opcode = int(rest[:2], 16)
        body = rest.split(":", 1)[1].strip() if is_text else rest[rest.index("(") + 1 : rest.rindex(")")]
        buffer = (line_number, opcode, body, is_text)
    flush()
