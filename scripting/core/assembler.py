"""Two-pass assembler: pass 1 places labels, pass 2 encodes every item."""

from dataclasses import dataclass

from errors import ScriptAssemblyError
from scripting.core.items import Data, Instruction, Label, Script
from scripting.core.language import OpcodeSpec
from scripting.core.operands import Layout, OperandKind


@dataclass(frozen=True)
class Assembled:
    data: bytes
    labels: dict[str, int]
    """Byte position of each label, relative to the first byte of ``data``."""


def operand_pairs(spec: OpcodeSpec, instruction: Instruction) -> list[tuple[OperandKind, object]]:
    if len(instruction.operands) != len(spec.operands):
        msg = f"{spec.name} takes {len(spec.operands)} operands, got {len(instruction.operands)}."
        raise ScriptAssemblyError(msg)
    return list(zip(spec.operands, instruction.operands, strict=True))


def _place_labels(script: Script) -> tuple[dict[str, int], int]:
    labels: dict[str, int] = {}
    position = 0
    for item in script.body:
        if isinstance(item, Label):
            if item.name in labels:
                msg = f"Duplicate label: {item.name!r}"
                raise ScriptAssemblyError(msg)
            labels[item.name] = position
        elif isinstance(item, Data):
            position += len(item.raw)
        else:
            spec = script.language.spec(item.opcode)
            position += 1 + sum(kind.size(value) for kind, value in operand_pairs(spec, item))
    return labels, position


def assemble(script: Script, origin: int, *, max_size: int | None = None) -> Assembled:
    """Encode ``script``. A jump to label position ``p`` encodes ``origin + p``."""
    labels, size = _place_labels(script)
    if max_size is not None and size > max_size:
        msg = f"Assembled script is {size} bytes, exceeds max_size {max_size}."
        raise ScriptAssemblyError(msg)
    layout = Layout(origin, labels)
    out = bytearray()
    for item in script.body:
        if isinstance(item, Data):
            out += item.raw
        elif isinstance(item, Instruction):
            out.append(item.opcode)
            for kind, value in operand_pairs(script.language.spec(item.opcode), item):
                out += kind.encode(value, layout)
    assert len(out) == size
    return Assembled(bytes(out), labels)
