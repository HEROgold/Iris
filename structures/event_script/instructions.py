"""The structured instruction model produced by the parser.

An :class:`EventScript` owns a ``list[Instruction]``. Each :class:`Instruction` carries its byte
offset within the script (its dump *label*), the opcode, and a flat list of typed operands.

Operands are one of:

- ``int`` -- a fixed-width integer operand (the width is dictated by the opcode's operand shape).
- :class:`Address` -- a local jump target (an offset within the same script), rendered ``@XXXX``.
- ``list[TextChunk]`` -- a decoded dialogue/text stream (only for text opcodes).

For ``pointers`` opcodes the first operand is the count ``int`` followed by that many
:class:`Address` operands. For the ``0x14`` ``variable`` condition chain the operands are the flat
sequence of sub-code ints and :class:`Address` branch targets, terminated by ``0xFF``.
"""

from dataclasses import dataclass, field


@dataclass
class Address:
    """A local jump target: an offset within the same script. Rendered ``@XXXX`` in dumps.

    Only local addresses are supported (mirroring terrorwave's ``Script.Address``); a non-local
    target raises on construction.
    """

    offset: int
    is_local: bool = True

    def __post_init__(self) -> None:
        if not self.is_local:
            msg = f"Non-local address: {self.offset:#x}"
            raise NotImplementedError(msg)
        if not 0 <= self.offset <= 0x7FFF:
            msg = f"Address offset out of range: {self.offset:#x}"
            raise ValueError(msg)

    def __repr__(self) -> str:
        return f"@{self.offset:X}"


@dataclass
class TextChunk:
    """A single decoded piece of a text stream.

    ``tag`` is either a control-code ``int`` (a byte in the ``CHARACTER_MAP``), one of the string
    tags ``"NPC"`` / ``"POSITION"`` (leading text-opcode operands), or ``None`` for a literal run.
    ``data`` holds the literal bytes of a run, or the raw parameter bytes of a tagged chunk.
    """

    tag: int | str | None
    data: bytes = b""


type Operand = int | Address | list[TextChunk]


@dataclass
class Instruction:
    """One opcode plus its typed operands, tagged with its byte offset within the script."""

    line: int
    opcode: int
    operands: list[Operand] = field(default_factory=list)
