"""Text compression for event scripts that move (``compile_script(compress=True)``, ``codec.RepeatWindow``).

A script compiled this way must say exactly what it said before, and its ``<REPEAT>`` back-references may only copy
the script's own earlier text: parsing it with nothing in front of it (an empty ``_pre`` window) must still give the
same text, so it reads the same wherever it is placed.
"""

from iris.structures.event_script import MapEvent
from iris.structures.event_script.codec import REPEAT_CODE, RepeatWindow, resolve_repeat
from iris.structures.event_script.compiler import compile_script
from iris.structures.event_script.instructions import Address
from iris.structures.event_script.script import EventScript
from iris.tables import MapEventObject


def _scripts() -> list[EventScript]:
    scripts = []
    for index in range(MapEventObject.count):
        map_event = MapEvent.from_index(index)
        map_event.read()
        scripts.extend(script for event_list in map_event.event_lists for script in event_list.events if script.instructions)
    return scripts


def _flatten(script: EventScript) -> list[tuple[int, list[object]]]:
    """Each instruction as (opcode, operands), with text as its expanded bytes and jumps as instruction numbers."""
    numbers = {instruction.line: number for number, instruction in enumerate(script.instructions)}
    out = []
    for instruction in script.instructions:
        operands: list[object] = []
        for operand in instruction.operands:
            if isinstance(operand, list):
                text = b"".join(
                    chunk.data if chunk.tag is None else str(chunk.tag).encode() + chunk.data for chunk in operand
                )
                operands.append(text)
            elif isinstance(operand, Address) and operand.is_local:
                operands.append(("jump", min(number for line, number in numbers.items() if line >= operand.offset)))
            else:
                operands.append(operand)
        out.append((instruction.opcode, operands))
    return out


def _reparse(script: EventScript, data: bytes) -> EventScript:
    """``data`` parsed as ``script`` would be at its own address, with nothing readable in front of it."""
    copy = EventScript(script.base_pointer, script.offset, script.index, script.event_class)
    copy.raw = data
    copy.instructions = copy._parse(data)  # noqa: SLF001 (no ROM read: _pre stays empty)
    return copy


def test_every_vanilla_script_reads_the_same_after_compression() -> None:
    for script in _scripts():
        data = compile_script(script, script_pointer=script.pointer, compress=True)
        assert _flatten(_reparse(script, data)) == _flatten(script), script


def test_compressed_length_does_not_depend_on_addresses() -> None:
    """The relocator sizes a script with ``ignore_pointers`` before its address is known."""
    for script in _scripts():
        sized = compile_script(script, ignore_pointers=True, compress=True)
        placed = compile_script(script, script_pointer=script.pointer, compress=True)
        assert len(sized) == len(placed), script


def test_compression_stays_close_to_vanilla() -> None:
    """Vanilla's back-references may reach into the neighbouring scripts, which a moved script can't; the
    script-local ones cost a little (73 bytes over 226KB when written), never much."""
    original = compressed = 0
    for script in _scripts():
        original += len(script.raw)
        compressed += len(compile_script(script, ignore_pointers=True, compress=True))
    assert compressed <= original * 1.001


def test_repeat_window_copies_earlier_text() -> None:
    window = RepeatWindow()
    text = b"Hello there. Hello there."
    out = bytes(window.compress(text))
    assert REPEAT_CODE in out
    assert len(out) < len(text)
    position = out.index(REPEAT_CODE)
    assert out[:position] + resolve_repeat(out[: position + 3], out[position + 1 : position + 3]) == text


def test_repeat_window_never_copies_codes() -> None:
    """Word codes, control codes and everything else outside plain ASCII are never part of a copy."""
    window = RepeatWindow()
    window.skip(20)  # an opcode and its operands: not text
    text = b"\x05\x10abc\x03\x05\x10abc\x03"
    assert bytes(window.compress(text)) == text


def test_repeat_window_needs_four_bytes() -> None:
    """A back-reference costs 3 bytes, so a 3-byte copy is left as text."""
    window = RepeatWindow()
    assert bytes(window.compress(b"abc abc")) == b"abc abc"
