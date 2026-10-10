"""Operand kinds of scripting.core: decode, encode, size and render."""

import pytest

from errors import ScriptAssemblyError, ScriptDecodeError
from scripting.core import U8, U16, DecodeContext, External, Jump, Label, Layout, label_name


def test_u8_round_trip() -> None:
    ctx = DecodeContext(origin=0, span=range(0))
    value, pos = U8("reg").decode(bytes([0x12, 0x80]), 1, ctx)
    assert (value, pos) == (0x80, 2)
    assert U8("reg").encode(0x80, Layout(0, {})) == b"\x80"
    assert U8("reg").render(0x80) == "reg=$80"


def test_u16_is_little_endian() -> None:
    ctx = DecodeContext(origin=0, span=range(0))
    assert U16().decode(bytes([0x34, 0x12]), 0, ctx) == (0x1234, 2)
    assert U16().encode(0x1234, Layout(0, {})) == b"\x34\x12"


@pytest.mark.parametrize(("kind", "value"), [(U8(), 0x100), (U8(), -1), (U16(), 0x10000), (U8(), "x")])
def test_out_of_range_values_raise(kind: U8 | U16, value: object) -> None:
    with pytest.raises(ScriptAssemblyError):
        kind.encode(value, Layout(0, {}))


def test_truncated_operand_raises_decode_error() -> None:
    with pytest.raises(ScriptDecodeError):
        U16().decode(b"\x01", 0, DecodeContext(origin=0, span=range(0)))


def test_jump_inside_span_becomes_a_label() -> None:
    ctx = DecodeContext(origin=0x2B, span=range(0x40))
    value, pos = Jump().decode((0x2B + 0x10).to_bytes(2, "little"), 0, ctx)
    assert value == Label("L_0010")
    assert pos == 2
    assert ctx.offsets == {"L_0010": 0x10}


def test_jump_outside_span_becomes_external() -> None:
    ctx = DecodeContext(origin=0, span=range(0x10))
    value, _ = Jump().decode((0x30).to_bytes(2, "little"), 0, ctx)
    assert value == External(0x30)
    assert ctx.offsets == {}


def test_jump_encodes_origin_plus_label_position() -> None:
    layout = Layout(origin=0x2B, labels={"out": 7})
    assert Jump().encode(Label("out"), layout) == (0x2B + 7).to_bytes(2, "little")
    assert Jump().encode(External(0x1234), layout) == b"\x34\x12"


def test_undefined_label_raises() -> None:
    with pytest.raises(ScriptAssemblyError, match="Undefined label: 'nowhere'"):
        Jump().encode(Label("nowhere"), Layout(0, {}))


def test_jump_value_outside_u16_raises() -> None:
    with pytest.raises(ScriptAssemblyError, match="outside u16"):
        Jump().encode(Label("far"), Layout(0xFFFF, {"far": 1}))


def test_label_name_format() -> None:
    assert label_name(0x47) == "L_0047"
