"""Parse an L2BASM record into one Script that covers every entry point.

A record's scripts keep handler blocks after the first END that only jumps reach, and some monsters share blocks
between attack and defense. So the parser walks from every entry point, follows each opcode's Flow, and emits one
body covering the first to the last reached byte. Unreached bytes in between become Data, so assembling the body
reproduces the record bytes exactly.
"""

import logging
from collections.abc import Mapping
from dataclasses import dataclass

from errors import ScriptDecodeError
from logger import iris
from scripting.core import Data, DecodeContext, External, Flow, Instruction, Item, Label, OpcodeSpec, Script
from scripting.l2basm.opcodes import L2BASM


log = logging.getLogger(f"{iris.name}.L2BASM.Parser")


@dataclass(frozen=True)
class ParsedRecord:
    script: Script
    start: int
    """Record offset of the script's first byte; assemble with ``origin=start``."""
    end: int
    """Record offset one past the script's last byte."""


def _decode_at(record: bytes, pos: int, ctx: DecodeContext) -> tuple[Instruction, int, OpcodeSpec] | None:
    spec = L2BASM.find(record[pos])
    if spec is None:
        log.warning("Unknown L2BASM opcode %#04x at record offset %#x; ending this path.", record[pos], pos)
        return None
    trial = DecodeContext(ctx.origin, ctx.span)
    operands: list[object] = []
    cursor = pos + 1
    try:
        for kind in spec.operands:
            value, cursor = kind.decode(record, cursor, trial)
            operands.append(value)
    except ScriptDecodeError:
        log.warning("Opcode %#04x at record offset %#x runs past the record; ending this path.", spec.opcode, pos)
        return None
    ctx.offsets.update(trial.offsets)
    return Instruction(spec.opcode, operands), cursor - pos, spec


def _walk(record: bytes, entries: Mapping[str, int], ctx: DecodeContext) -> dict[int, tuple[Instruction, int]]:
    decoded: dict[int, tuple[Instruction, int]] = {}
    stack = list(entries.values())
    while stack:
        pos = stack.pop()
        while 0 <= pos < len(record) and pos not in decoded:
            step = _decode_at(record, pos, ctx)
            if step is None:
                break
            instruction, size, spec = step
            decoded[pos] = (instruction, size)
            jumps = [ctx.offsets[value.name] for value in instruction.operands if isinstance(value, Label)]
            if spec.flow is Flow.END:
                break
            if spec.flow is Flow.GOTO:
                if not jumps:
                    break
                pos = jumps[0]
                continue
            if spec.flow is Flow.BRANCH:
                stack.extend(jumps)
            pos += size
    return decoded


def _body(
    record: bytes,
    decoded: dict[int, tuple[Instruction, int]],
    start: int,
    end: int,
    labels_at: dict[int, list[str]],
) -> tuple[list[Item], set[str]]:
    body: list[Item] = []
    placed: set[str] = set()
    pending = bytearray()

    def flush() -> None:
        if pending:
            body.append(Data(bytes(pending)))
            pending.clear()

    pos = start
    while pos < end:
        if pos in labels_at:
            flush()
            body.extend(Label(name) for name in labels_at[pos])
            placed.update(labels_at[pos])
        if pos in decoded:
            flush()
            instruction, size = decoded[pos]
            body.append(instruction)
            pos += size
        else:
            pending.append(record[pos])
            pos += 1
    flush()
    if end in labels_at:
        body.extend(Label(name) for name in labels_at[end])
        placed.update(labels_at[end])
    return body, placed


def parse_record(
    record: bytes,
    entries: Mapping[str, int],
    *,
    start: int | None = None,
    origin: int = 0,
) -> ParsedRecord:
    """Parse ``record`` from every offset in ``entries`` (entry name -> record offset)."""
    if not entries:
        msg = "parse_record needs at least one entry point."
        raise ValueError(msg)
    ctx = DecodeContext(origin=origin, span=range(len(record) + 1))
    decoded = _walk(record, entries, ctx)
    if not decoded:
        msg = f"No instruction decoded from entries {dict(entries)}."
        raise ValueError(msg)
    first = min(decoded) if start is None else start
    end = max(pos + size for pos, (_, size) in decoded.items())
    labels_at: dict[int, list[str]] = {}
    for name, offset in entries.items():
        labels_at.setdefault(offset, []).append(name)
    for name, offset in sorted(ctx.offsets.items(), key=lambda pair: pair[1]):
        if name not in labels_at.get(offset, []):
            labels_at.setdefault(offset, []).append(name)
    body, placed = _body(record, decoded, first, end, labels_at)
    for item in body:
        if isinstance(item, Instruction):
            item.operands = [
                External(origin + ctx.offsets[value.name])
                if isinstance(value, Label) and value.name not in placed
                else value
                for value in item.operands
            ]
    return ParsedRecord(Script(L2BASM, body), first, end)
