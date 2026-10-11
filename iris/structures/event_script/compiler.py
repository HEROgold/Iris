"""Compile a structured :class:`EventScript` back into bytecode, recomputing every pointer.

This is the write path for *modified* scripts (Mode B). Unmodified scripts never reach here -- they
write verbatim (Mode A) in :meth:`EventScript.write`. The algorithm mirrors terrorwave's
``Script.compile``: lay out each instruction's bytes, record ``line_number -> byte_offset``, then
rewrite each :class:`Address` placeholder to its real 2-byte little-endian value.

Text is emitted chunk-by-chunk exactly as decoded (literal runs, word codes and control codes keep their
original bytes), so an unchanged script compiles back to its original bytes. A literal run decoded from
a ``<REPEAT>`` back-reference is re-emitted as that back-reference only while it still expands to the
same bytes in the new output; otherwise (e.g. an earlier edit shifted the window) it is written literally.

With ``compress=True`` the original back-references are dropped and the text is compressed again, copying only the
script's own earlier text (:class:`codec.RepeatWindow`). The result doesn't depend on the bytes in front of the script,
so it is what a script must be compiled with when it moves, and it is usually smaller than the original.

Compile once with ``ignore_pointers=True`` to measure the length, allocate, then compile again with
the real ``script_pointer`` to fix the offsets.
"""

from typing import TYPE_CHECKING

from iris.structures.event_script.codec import REPEAT_CODE, RepeatWindow, resolve_repeat
from iris.structures.event_script.instructions import Address, Instruction, TextChunk
from iris.structures.event_script.opcodes import ADDR, POINTERS, TEXT, VARIABLE, operand_shape


if TYPE_CHECKING:
    from iris.structures.event_script.script import EventScript


type Token = int | Address | bytes
"""A byte, a jump target (2 bytes), or a literal text run still to be compressed (``compress=True`` only)."""


def _emit_text(
    line: list[Token],
    chunks: list[TextChunk],
    repeats: list[tuple[int, TextChunk]],
    literal: set[int],
    *,
    compress: bool,
) -> None:
    """Emit ``chunks`` byte-for-byte, recording each re-emitted ``<REPEAT>`` as ``(token index, chunk)``.

    With ``compress``, literal runs (back-references expanded) stay whole ``bytes`` tokens for :func:`_compress`.
    """
    for chunk in chunks:
        if chunk.tag is None:
            if compress:
                line.append(chunk.data)
            elif chunk.repeat is not None and id(chunk) not in literal:
                repeats.append((len(line), chunk))
                line.append(REPEAT_CODE)
                line.extend(chunk.repeat)
            else:
                line.extend(chunk.data)
        elif isinstance(chunk.tag, str):  # "NPC" / "POSITION": the text opcode's leading operands
            line.extend(chunk.data)
        else:
            line.append(chunk.tag)
            line.extend(chunk.data)


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


def _emit_instruction(
    instruction: Instruction,
    repeats: list[tuple[int, TextChunk]],
    literal: set[int],
    *,
    compress: bool,
) -> list[Token]:
    line: list[Token] = [instruction.opcode]
    shape = operand_shape(instruction.opcode)
    operand_index = 0
    for token in shape:
        if token == TEXT:
            chunks = instruction.operands[operand_index]
            if not isinstance(chunks, list):
                msg = "Text operand expected."
                raise TypeError(msg)
            _emit_text(line, chunks, repeats, literal, compress=compress)
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
    return sum(2 if isinstance(tok, Address) else len(tok) if isinstance(tok, bytes) else 1 for tok in line)


def _compress(partial: dict[int, list[Token]], ordered: list[int]) -> None:
    """Replace every literal text run, in output order, with its compressed bytes (see :class:`RepeatWindow`)."""
    window = RepeatWindow()
    for line_number in ordered:
        line: list[Token] = []
        for tok in partial[line_number]:
            if isinstance(tok, bytes):
                line.extend(window.compress(tok))
            else:
                window.skip(2 if isinstance(tok, Address) else 1)
                line.append(tok)
        partial[line_number] = line


def compile_script(
    script: "EventScript",
    script_pointer: int | None = None,
    *,
    ignore_pointers: bool = False,
    compress: bool = False,
) -> bytes:
    """Emit the script's bytecode, resolving every local :class:`Address` to a 2-byte offset.

    Compiles, then checks every re-emitted ``<REPEAT>`` against the output; any that no longer expands
    to its original text is demoted to a literal run and the script is recompiled (only ever shrinking
    the set of back-references, so this terminates). With ``compress``, the text is compressed again from scratch
    instead (see the module docstring), so there is nothing to check.
    """
    literal: set[int] = set()
    while True:
        out, repeats = _compile(script, script_pointer, literal, ignore_pointers=ignore_pointers, compress=compress)
        broken = [
            chunk
            for position, chunk in repeats
            if resolve_repeat(script._pre + out[: position + 3], chunk.repeat or b"") != chunk.data
        ]
        if not broken:
            return out
        literal.update(id(chunk) for chunk in broken)


def _compile(
    script: "EventScript",
    script_pointer: int | None,
    literal: set[int],
    *,
    ignore_pointers: bool,
    compress: bool,
) -> tuple[bytes, list[tuple[int, TextChunk]]]:
    """One compile pass; also returns each re-emitted ``<REPEAT>`` as ``(byte offset, chunk)``."""
    partial: dict[int, list[Token]] = {}
    line_repeats: dict[int, list[tuple[int, TextChunk]]] = {}
    previous = None
    for instruction in script.instructions:
        if previous is not None and instruction.line <= previous:
            msg = "Instruction line numbers must be strictly ascending."
            raise ValueError(msg)
        previous = instruction.line
        line_repeats[instruction.line] = []
        partial[instruction.line] = _emit_instruction(
            instruction, line_repeats[instruction.line], literal, compress=compress,
        )

    ordered = sorted(partial)
    _compress(partial, ordered)  # only compress=True emits literal runs to compress; otherwise nothing changes
    conversions: dict[int, int] = {}
    repeats: list[tuple[int, TextChunk]] = []
    running = 0
    for line_number in ordered:
        conversions[line_number] = running
        line = partial[line_number]
        repeats.extend((running + _byte_length(line[:index]), chunk) for index, chunk in line_repeats[line_number])
        running += _byte_length(line)

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
                # A non-local jump keeps its raw operand: its target lies outside this script.
                value = _snap(conversions, tok.offset) + script_offset if tok.is_local else tok.offset
                if not 0 <= value <= 0xFFFF:
                    msg = f"Resolved address out of range: {value:#x}"
                    raise ValueError(msg)
                out.append(value & 0xFF)
                out.append(value >> 8)
            elif isinstance(tok, bytes):
                out.extend(tok)
            else:
                out.append(tok & 0xFF)
    return bytes(out), repeats


def _snap(conversions: dict[int, int], target: int) -> int:
    """Snap ``target`` to the nearest existing line number >= it (drops redundant fall-throughs)."""
    if target in conversions:
        return conversions[target]
    for line_number in sorted(conversions):
        if line_number >= target:
            return conversions[line_number]
    msg = f"Address target {target:#x} beyond script."
    raise ValueError(msg)
