"""Operand kinds: how one operand decodes from bytes, how big it is, and how it encodes.

``size`` never depends on where labels land, so two assembler passes always resolve every jump.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from errors import ScriptAssemblyError, ScriptDecodeError
from scripting.core.items import External, Label, Target


def label_name(offset: int) -> str:
    """The name the parsers give a jump target at ``offset``."""
    return f"L_{offset:04X}"


@dataclass(frozen=True)
class Layout:
    """Label positions from assembler pass 1, plus the value a jump to position 0 encodes."""

    origin: int
    labels: Mapping[str, int]

    def resolve(self, target: Target) -> int:
        if isinstance(target, External):
            return target.value
        if target.name not in self.labels:
            msg = f"Undefined label: {target.name!r}"
            raise ScriptAssemblyError(msg)
        value = self.origin + self.labels[target.name]
        if not 0 <= value <= 0xFFFF:
            msg = f"Jump to {target.name!r} resolves to {value:#x}, outside u16."
            raise ScriptAssemblyError(msg)
        return value


@dataclass
class DecodeContext:
    """Parser state for jump operands: jump values whose target offset is in ``span`` become labels."""

    origin: int
    span: range
    offsets: dict[str, int] = field(default_factory=dict)

    def target(self, value: int) -> Target:
        offset = value - self.origin
        if offset in self.span:
            name = label_name(offset)
            self.offsets[name] = offset
            return Label(name)
        return External(value)


class OperandKind(Protocol):
    def decode(self, data: bytes, pos: int, ctx: DecodeContext) -> tuple[object, int]: ...
    def size(self, value: object) -> int: ...
    def encode(self, value: object, layout: Layout) -> bytes: ...
    def render(self, value: object) -> str: ...


def _take(data: bytes, pos: int, width: int) -> bytes:
    chunk = data[pos : pos + width]
    if len(chunk) != width:
        msg = f"Operand at {pos:#x} needs {width} bytes, only {len(chunk)} left."
        raise ScriptDecodeError(msg)
    return chunk


def _checked_int(value: object, limit: int, role: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= limit:
        msg = f"Operand {role} must be an int in [0, {limit:#x}], got {value!r}."
        raise ScriptAssemblyError(msg)
    return value


@dataclass(frozen=True)
class U8:
    role: str = "u8"

    def decode(self, data: bytes, pos: int, ctx: DecodeContext) -> tuple[object, int]:  # noqa: ARG002
        return _take(data, pos, 1)[0], pos + 1

    def size(self, value: object) -> int:  # noqa: ARG002
        return 1

    def encode(self, value: object, layout: Layout) -> bytes:  # noqa: ARG002
        return bytes([_checked_int(value, 0xFF, self.role)])

    def render(self, value: object) -> str:
        return f"{self.role}=${value:02X}"


@dataclass(frozen=True)
class U16:
    role: str = "u16"

    def decode(self, data: bytes, pos: int, ctx: DecodeContext) -> tuple[object, int]:  # noqa: ARG002
        return int.from_bytes(_take(data, pos, 2), "little"), pos + 2

    def size(self, value: object) -> int:  # noqa: ARG002
        return 2

    def encode(self, value: object, layout: Layout) -> bytes:  # noqa: ARG002
        return _checked_int(value, 0xFFFF, self.role).to_bytes(2, "little")

    def render(self, value: object) -> str:
        return f"{self.role}=${value:04X}"


@dataclass(frozen=True)
class Jump:
    role: str = "to"

    def decode(self, data: bytes, pos: int, ctx: DecodeContext) -> tuple[object, int]:
        return ctx.target(int.from_bytes(_take(data, pos, 2), "little")), pos + 2

    def size(self, value: object) -> int:  # noqa: ARG002
        return 2

    def encode(self, value: object, layout: Layout) -> bytes:
        if not isinstance(value, Label | External):
            msg = f"Jump operand must be a Label or External, got {value!r}."
            raise ScriptAssemblyError(msg)
        return layout.resolve(value).to_bytes(2, "little")

    def render(self, value: object) -> str:
        if isinstance(value, Label):
            return value.name
        assert isinstance(value, External)
        return f"${value.value:04X}"
