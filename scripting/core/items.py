"""The items a script body is made of: instructions, labels and raw data."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from scripting.core.language import Language


@dataclass(frozen=True)
class Label:
    """A zero-width position in a script. Jumps name it; the assembler resolves it."""

    name: str


@dataclass(frozen=True)
class External:
    """A jump target outside the script. The assembler writes ``value`` unchanged."""

    value: int


type Target = Label | External


@dataclass
class Instruction:
    """One opcode and its operand values. The language's ``OpcodeSpec`` says how to encode them."""

    opcode: int
    operands: list[object] = field(default_factory=list)


@dataclass
class Data:
    """Bytes kept verbatim: parts of a record the parser didn't decode, or deliberate raw bytes."""

    raw: bytes


type Item = Instruction | Label | Data


@dataclass
class Script:
    """A body of items in one language. Parsed and hand-written scripts are both this."""

    language: "Language"
    body: list[Item] = field(default_factory=list)
