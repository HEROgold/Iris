"""The L2BASM opcode table: operand widths, flows and known corrections."""

import pytest

from scripting.core import Flow
from scripting.l2basm.opcodes import CORRECTIONS, L2BASM, PARAM_COUNTS


@pytest.mark.parametrize("opcode", sorted(L2BASM.opcodes))
def test_operand_widths_add_up_to_the_documented_count(opcode: int) -> None:
    spec = L2BASM.opcodes[opcode]
    widths = sum(kind.size(0) for kind in spec.operands)
    assert widths == PARAM_COUNTS[opcode], f"{spec.name}: operands {widths} bytes, table says {PARAM_COUNTS[opcode]}"


def test_rand_takes_one_operand_byte() -> None:
    assert CORRECTIONS[0x11] == 1
    assert PARAM_COUNTS[0x11] == 1


def test_cast_spell_is_known() -> None:
    assert L2BASM.spec(0x2C).name == "cast_spell"


@pytest.mark.parametrize(
    ("opcode", "flow"),
    [(0x00, Flow.END), (0x43, Flow.END), (0x03, Flow.GOTO), (0x04, Flow.BRANCH), (0x05, Flow.BRANCH),
     (0x06, Flow.BRANCH), (0x0B, Flow.BRANCH), (0x3F, Flow.BRANCH), (0x28, Flow.CONTINUE)],
)
def test_flows(opcode: int, flow: Flow) -> None:
    assert L2BASM.spec(opcode).flow is flow


def test_jump_operands_sit_where_the_game_reads_them() -> None:
    # byte index of the jump inside the operands, from the old JUMP_OPERAND table
    expected = {0x03: 0, 0x04: 0, 0x05: 1, 0x06: 3, 0x0B: 3, 0x3F: 1}
    for opcode, byte_index in expected.items():
        spec = L2BASM.spec(opcode)
        (index,) = spec.jump_indices
        assert sum(kind.size(0) for kind in spec.operands[:index]) == byte_index
