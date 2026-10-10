"""Opcode tables: each language maps opcode bytes to an ``OpcodeSpec``."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, auto

from errors import ScriptAssemblyError
from scripting.core.operands import Jump, OperandKind


class Flow(Enum):
    """What happens after an instruction; the parsers follow this."""

    CONTINUE = auto()  # fall through to the next instruction
    END = auto()  # the path ends
    GOTO = auto()  # jump unconditionally to the Jump operand
    BRANCH = auto()  # maybe jump to the Jump operand, else fall through


@dataclass(frozen=True)
class OpcodeSpec:
    opcode: int
    name: str
    operands: tuple[OperandKind, ...] = ()
    flow: Flow = Flow.CONTINUE
    comment: str = ""

    @property
    def jump_indices(self) -> tuple[int, ...]:
        return tuple(i for i, kind in enumerate(self.operands) if isinstance(kind, Jump))


@dataclass(frozen=True)
class Language:
    name: str
    opcodes: Mapping[int, OpcodeSpec]

    def find(self, opcode: int) -> OpcodeSpec | None:
        return self.opcodes.get(opcode)

    def spec(self, opcode: int) -> OpcodeSpec:
        spec = self.find(opcode)
        if spec is None:
            msg = f"{self.name} has no opcode {opcode:#04x}."
            raise ScriptAssemblyError(msg)
        return spec
