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
    """A jump target. Rendered ``@XXXX`` (local) or ``$XXXX`` (non-local) in dumps.

    A local target is an offset within the same script, so the compiler can move it with the script's lines. A
    non-local one jumps out of the script: ``offset`` is then the raw operand, relative to the map's base pointer.
    Vanilla has none; FRUE has three, each into shared code a few bytes inside the neighbouring talk script. They
    are written back unchanged, which is only right while the target stays where it is (see
    ``EventScript.jumped_into`` and ``MapEvent.write_relocated``).
    """

    offset: int
    is_local: bool = True

    def __post_init__(self) -> None:
        limit = 0x7FFF if self.is_local else 0xFFFF
        if not 0 <= self.offset <= limit:
            msg = f"Address offset out of range: {self.offset:#x}"
            raise ValueError(msg)

    def __repr__(self) -> str:
        return f"@{self.offset:X}" if self.is_local else f"${self.offset:X}"


@dataclass
class TextChunk:
    """A single decoded piece of a text stream.

    ``tag`` is either a control-code ``int`` (a byte in the ``CHARACTER_MAP``), one of the string
    tags ``"NPC"`` / ``"POSITION"`` (leading text-opcode operands), or ``None`` for a literal run.
    ``data`` holds the literal bytes of a run, or the raw parameter bytes of a tagged chunk.
    ``repeat`` is set on a literal run that was decoded from a ``0x0A`` ``<REPEAT>`` back-reference:
    its 2 parameter bytes, so the compiler can re-emit the back-reference when it still resolves.
    """

    tag: int | str | None
    data: bytes = b""
    repeat: bytes | None = None


type Operand = int | Address | list[TextChunk]


@dataclass
class Instruction:
    """One opcode plus its typed operands, tagged with its byte offset within the script."""

    line: int
    opcode: int
    operands: list[Operand] = field(default_factory=list)
