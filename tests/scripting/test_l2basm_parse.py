"""parse_record on hand-made records: walking, labels, Data gaps, shared blocks, External targets."""

from scripting.core import Data, External, Instruction, Label, assemble
from scripting.l2basm import parse_record


def _hex(text: str) -> bytes:
    return bytes.fromhex(text)


def _round_trips(record: bytes, entries: dict[str, int], start: int | None = None) -> None:
    parsed = parse_record(record, entries, start=start)
    assert assemble(parsed.script, parsed.start).data == record[parsed.start : parsed.end]


def test_simple_chance_skip() -> None:
    # header(2) | 32 01 | 05 10 0A 00 | 28 | 00      -> the chance jump goes to +0x0A (one past the END)
    record = _hex("AA BB 32 01 05 10 0A 00 28 00")
    parsed = parse_record(record, {"attack": 2})
    assert (parsed.start, parsed.end) == (2, 10)
    body = parsed.script.body
    assert body[0] == Label("attack")
    assert body[2] == Instruction(0x05, [0x10, Label("L_000A")])
    assert body[-1] == Label("L_000A")
    _round_trips(record, {"attack": 2})


def test_handler_blocks_after_end_are_reached_through_jumps() -> None:
    # 05 30 08 00 | 00 | 28 00 | 00 ; the block at +5 is only reachable through... nothing; +8 via the chance
    record = _hex("05 30 08 00 00 28 00 00 29 00")
    parsed = parse_record(record, {"attack": 0})
    assert parsed.end == 10
    assert Data(_hex("28 00 00")) in parsed.script.body
    assert Label("L_0008") in parsed.script.body
    _round_trips(record, {"attack": 0})


def test_goto_is_followed_not_fallen_through() -> None:
    record = _hex("03 05 00 FF FF 28 00")
    parsed = parse_record(record, {"attack": 0})
    assert Data(_hex("FF FF")) in parsed.script.body
    _round_trips(record, {"attack": 0})


def test_two_entries_share_a_block() -> None:
    # attack: 03 06 00 (goto shared) ; defense at +3: 03 06 00 ; shared at +6: 28 00
    record = _hex("03 06 00 03 06 00 28 00")
    parsed = parse_record(record, {"attack": 0, "defense": 3})
    names = [item.name for item in parsed.script.body if isinstance(item, Label)]
    assert names == ["attack", "defense", "L_0006"]
    _round_trips(record, {"attack": 0, "defense": 3})


def test_jump_outside_the_record_is_external() -> None:
    record = _hex("04 00 01 00")
    parsed = parse_record(record, {"attack": 0})
    assert parsed.script.body[1] == Instruction(0x04, [External(0x100)])
    _round_trips(record, {"attack": 0})


def test_jump_into_the_middle_of_an_instruction_is_external() -> None:
    # 0C 80 34 12 is set_reg(0x80, 0x1234); the chance jumps to +2, inside it
    record = _hex("0C 80 34 12 05 10 02 00 00")
    parsed = parse_record(record, {"attack": 0})
    assert Instruction(0x05, [0x10, External(2)]) in parsed.script.body
    assert "L_0002" not in [item.name for item in parsed.script.body if isinstance(item, Label)]
    _round_trips(record, {"attack": 0})


def test_jump_into_the_header_is_external() -> None:
    record = _hex("AA BB 04 00 00 00")
    parsed = parse_record(record, {"attack": 2})
    assert Instruction(0x04, [External(0)]) in parsed.script.body
    _round_trips(record, {"attack": 2})


def test_unknown_opcode_ends_the_path_and_stays_data() -> None:
    record = _hex("28 FE 01 02 00")
    parsed = parse_record(record, {"attack": 0})
    assert parsed.end == 1
    _round_trips(record, {"attack": 0})


def test_explicit_start_keeps_gap_bytes_as_data() -> None:
    record = _hex("AA BB CC 28 00")
    parsed = parse_record(record, {"attack": 3}, start=2)
    assert parsed.start == 2
    assert parsed.script.body[0] == Data(_hex("CC"))
    _round_trips(record, {"attack": 3}, start=2)
