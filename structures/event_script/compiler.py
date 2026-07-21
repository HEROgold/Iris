"""Compile a structured :class:`EventScript` back into bytecode, recomputing every pointer.

This is the write path for *modified* scripts (Mode B). Unmodified scripts never reach here -- they
write verbatim (Mode A) in :meth:`EventScript.write`. The algorithm mirrors terrorwave's
``Script.compile``: lay out each instruction's bytes, record ``line_number -> byte_offset``, then
rewrite each :class:`Address` placeholder to its real 2-byte little-endian value.

Compile once with ``ignore_pointers=True`` to measure the length, allocate, then compile again with
the real ``script_pointer`` to fix the offsets.
"""

from typing import TYPE_CHECKING

from structures.event_script.codec import render_text
from structures.event_script.instructions import Address, Instruction, TextChunk
from structures.event_script.opcodes import ADDR, POINTERS, TEXT, VARIABLE, operand_shape


if TYPE_CHECKING:
    from structures.event_script.script import EventScript


type Token = int | Address


def _emit_text(line: list[Token], opcode: int, chunks: list[TextChunk]) -> None:
    from structures.event_script.codec import encode_text  # noqa: PLC0415

    data = encode_text(render_text(chunks), compress=opcode not in {0x6D, 0x6E})
    line.extend(data)


def _emit_variable(line: list[Token], operands: list[object], start: int) -> None:
    """Re-emit a ``0x14`` condition chain from its flat structured operands."""
    queue = list(operands[start:])
    while queue:
        code = queue.pop(0)
        if not isinstance(code, int):
            msg = "Malformed variable chain."
            raise TypeError(msg)
        line.append(code)
        if code == 0xFF:
            break
        if code & 0xF0 == 0xF0 or code & 0xF0 == 0x10:
            line.append(int(queue.pop(0)))
            line.append(int(queue.pop(0)))
        elif code & 0xF0 == 0xC0:
            line.extend(int(queue.pop(0)).to_bytes(2, "little"))
            line.extend(int(queue.pop(0)).to_bytes(2, "little"))
        elif code & 0xE0 == 0x20:
            line.append(queue.pop(0))  # Address
        else:
            line.append(int(queue.pop(0)))


def _emit_instruction(instruction: Instruction) -> list[Token]:
    line: list[Token] = [instruction.opcode]
    shape = operand_shape(instruction.opcode)
    operand_index = 0
    for token in shape:
        if token == TEXT:
            chunks = instruction.operands[operand_index]
            if not isinstance(chunks, list):
                msg = "Text operand expected."
                raise TypeError(msg)
            _emit_text(line, instruction.opcode, chunks)
            operand_index += 1
        elif token == POINTERS:
            count = instruction.operands[operand_index]
            line.append(int(count))
            for j in range(int(count)):
                line.append(instruction.operands[operand_index + 1 + j])
            operand_index += 1 + int(count)
        elif token == VARIABLE:
            _emit_variable(line, instruction.operands, operand_index)
            operand_index = len(instruction.operands)
        elif token == ADDR:
            line.append(instruction.operands[operand_index])
            operand_index += 1
        else:
            value = instruction.operands[operand_index]
            line.extend(int(value).to_bytes(int(token), "little"))
            operand_index += 1
    return line


def _byte_length(line: list[Token]) -> int:
    return sum(2 if isinstance(tok, Address) else 1 for tok in line)


def compile_script(script: "EventScript", script_pointer: int | None = None, *, ignore_pointers: bool = False) -> bytes:
    """Emit the script's bytecode, resolving every local :class:`Address` to a 2-byte offset."""
    partial: dict[int, list[Token]] = {}
    previous = None
    for instruction in script.instructions:
        if previous is not None and instruction.line <= previous:
            msg = "Instruction line numbers must be strictly ascending."
            raise ValueError(msg)
        previous = instruction.line
        partial[instruction.line] = _emit_instruction(instruction)

    ordered = sorted(partial)
    conversions: dict[int, int] = {}
    running = 0
    for line_number in ordered:
        conversions[line_number] = running
        running += _byte_length(partial[line_number])

    base = script.base_pointer
    pointer = script_pointer if script_pointer is not None else script.pointer
    script_offset = pointer - base

    out = bytearray()
    for line_number in ordered:
        for tok in partial[line_number]:
            if isinstance(tok, Address):
                if ignore_pointers:
                    out.extend((0, 0))
                    continue
                target = _snap(conversions, tok.offset)
                value = target + script_offset
                if not 0 <= value <= 0xFFFF:
                    msg = f"Resolved address out of range: {value:#x}"
                    raise ValueError(msg)
                out.append(value & 0xFF)
                out.append(value >> 8)
            else:
                out.append(tok & 0xFF)
    return bytes(out)


def _snap(conversions: dict[int, int], target: int) -> int:
    """Snap ``target`` to the nearest existing line number >= it (drops redundant fall-throughs)."""
    if target in conversions:
        return conversions[target]
    for line_number in sorted(conversions):
        if line_number >= target:
            return conversions[line_number]
    msg = f"Address target {target:#x} beyond script."
    raise ValueError(msg)
