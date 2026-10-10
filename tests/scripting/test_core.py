"""scripting.core: two-pass assembly, labels, errors and listings, on a two-opcode test language."""

import pytest

from errors import ScriptAssemblyError
from scripting.core import (
    U8,
    Data,
    External,
    Flow,
    Instruction,
    Jump,
    Label,
    Language,
    OpcodeSpec,
    Script,
    assemble,
    listing,
)


TOY = Language(
    "toy",
    {
        0x00: OpcodeSpec(0x00, "end", flow=Flow.END),
        0x05: OpcodeSpec(0x05, "on_chance", (U8("chance"), Jump()), Flow.BRANCH),
        0x28: OpcodeSpec(0x28, "attack"),
    },
)


def _script(*items: object) -> Script:
    return Script(TOY, list(items))  # type: ignore[arg-type]


def test_labels_resolve_against_the_origin() -> None:
    script = _script(
        Instruction(0x05, [0x10, Label("out")]),
        Instruction(0x28),
        Instruction(0x00),
        Label("out"),
    )
    out = assemble(script, origin=0x2B)
    assert out.data == bytes([0x05, 0x10, 0x2B + 6, 0x00, 0x28, 0x00])
    assert out.labels == {"out": 6}


def test_same_script_at_another_origin_changes_only_jump_bytes() -> None:
    script = _script(Instruction(0x05, [0x10, Label("out")]), Instruction(0x00), Label("out"))
    first = assemble(script, origin=0x2B).data
    second = assemble(script, origin=0x5C).data
    assert [i for i in range(len(first)) if first[i] != second[i]] == [2]


def test_data_is_emitted_verbatim_and_counts_toward_positions() -> None:
    script = _script(Data(b"\xff"), Label("start"), Instruction(0x28), Instruction(0x00))
    out = assemble(script, origin=0)
    assert out.data == b"\xff\x28\x00"
    assert out.labels == {"start": 1}


def test_external_is_written_unchanged() -> None:
    script = _script(Instruction(0x05, [0x01, External(0x1234)]))
    assert assemble(script, origin=0).data == b"\x05\x01\x34\x12"


def test_duplicate_label_raises() -> None:
    with pytest.raises(ScriptAssemblyError, match="Duplicate label: 'x'"):
        assemble(_script(Label("x"), Instruction(0x00), Label("x")), origin=0)


def test_undefined_label_raises() -> None:
    with pytest.raises(ScriptAssemblyError, match="Undefined label"):
        assemble(_script(Instruction(0x05, [0x01, Label("nowhere")])), origin=0)


def test_max_size_raises() -> None:
    script = _script(Instruction(0x28), Instruction(0x28), Instruction(0x00))
    with pytest.raises(ScriptAssemblyError, match="3 bytes, exceeds max_size 2"):
        assemble(script, origin=0, max_size=2)


def test_wrong_operand_count_raises() -> None:
    with pytest.raises(ScriptAssemblyError, match="on_chance takes 2 operands, got 1"):
        assemble(_script(Instruction(0x05, [0x01])), origin=0)


def test_unknown_opcode_raises() -> None:
    with pytest.raises(ScriptAssemblyError, match="toy has no opcode 0x77"):
        assemble(_script(Instruction(0x77)), origin=0)


def test_assembler_never_adds_an_end() -> None:
    assert assemble(_script(Instruction(0x28)), origin=0).data == b"\x28"


def test_listing() -> None:
    script = _script(
        Data(b"\xff"),
        Label("attack"),
        Instruction(0x05, [0x10, Label("out")]),
        Instruction(0x28),
        Instruction(0x00),
        Label("out"),
    )
    assert listing(script) == (
        "    .data FF\n"
        "attack:\n"
        "    on_chance chance=$10, out\n"
        "    attack\n"
        "    end\n"
        "out:\n"
    )
