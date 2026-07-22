"""``EventScript`` -- parse a script's bytes into structured instructions and write them back.

Parsing is linear over the script's byte range (bounded by the next known pointer in the map), as
in terrorwave's ``Script.parse``: there is no recursive branch-following -- jumps become local
:class:`Address` operands. Two write modes exist:

- **Mode A (frozen):** an unmodified script is a no-op -- its bytes are already correct in the
  working ROM (a copy of the source), so byte-identity round-trips hold without re-writing anything.
- **Mode B (dirty):** a modified script is recompiled in place at its original pointer and must fit
  the original slot (the write path does not relocate scripts).
"""

import logging
from typing import TYPE_CHECKING

from enums.event_scripts import EventClass
from helpers.files import read_file, restore_pointer, write_file
from logger import iris
from structures.event_script.codec import PRE_DATA_SIZE, decode_text
from structures.event_script.instructions import Address, Instruction
from structures.event_script.opcodes import ADDR, POINTERS, TEXT, VARIABLE, operand_shape


if TYPE_CHECKING:
    from structures.event_script.instructions import Operand


log = logging.getLogger(f"{iris.name}.EventScript")

# Fallback bound when no later pointer is known (mirrors terrorwave's END sentinels).
MAX_SCRIPT_LENGTH = 0x8000


class EventScript:
    """A single event script: opcode/operand instructions parsed from a contiguous byte range."""

    def __init__(self, base_pointer: int, offset: int, index: int, event_class: EventClass) -> None:
        self.base_pointer = base_pointer
        self.offset = offset
        self.pointer = base_pointer + offset
        self.index = index  # -1 == the NPC-load script
        self.event_class = event_class
        self.instructions: list[Instruction] = []
        self.raw = b""
        self.dirty = False
        self._read = False
        self._pre = b""

    def __repr__(self) -> str:
        return f"EventScript(pointer={self.pointer:#07x}, class={self.event_class.name}, index={self.index})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EventScript):
            return NotImplemented
        return (
            self.base_pointer == other.base_pointer
            and self.offset == other.offset
            and self.index == other.index
            and self.event_class == other.event_class
        )

    def __hash__(self) -> int:
        return hash((self.base_pointer, self.offset, self.index, self.event_class))

    @property
    def script_offset(self) -> int:
        """Offset of this script's start relative to its ``base_pointer``."""
        return self.pointer - self.base_pointer

    @restore_pointer
    def _pre_data(self) -> bytes:
        pointer = max(self.pointer - PRE_DATA_SIZE, 0)
        read_file.seek(pointer)
        return read_file.read(self.pointer - pointer)

    @restore_pointer
    def read(self, end_pointer: int) -> None:
        """Read and parse the script's bytes, bounded above by ``end_pointer``."""
        if self._read:
            return
        length = end_pointer - self.pointer
        if not 0 < length <= MAX_SCRIPT_LENGTH:
            length = MAX_SCRIPT_LENGTH
        read_file.seek(self.pointer)
        self.raw = read_file.read(length)
        self._pre = self._pre_data()
        self.instructions = self._parse(self.raw)
        self._read = True

    def _make_address(self, data: bytes) -> Address:
        offset = int.from_bytes(data, "little")
        pointer = self.base_pointer + offset
        is_local = self.pointer <= pointer < self.pointer + len(self.raw)
        if is_local:
            return Address(offset - self.script_offset, is_local=True)
        # terrorwave only supports local addresses; surface non-local as a parse failure.
        return Address(pointer, is_local=False)

    def _parse(self, data: bytes) -> list[Instruction]:  # noqa: C901, PLR0912
        full = data
        instructions: list[Instruction] = []
        try:
            while data:
                consumed = len(full) - len(data)
                opcode, data = data[0], data[1:]
                shape = operand_shape(opcode)
                operands: list[Operand] = []
                for token in shape:
                    if token == TEXT:
                        chunks, data = decode_text(opcode, data, full, self._pre)
                        operands.append(chunks)
                    elif token == POINTERS:
                        count, data = data[0], data[1:]
                        operands.append(count)
                        for _ in range(count):
                            operands.append(self._make_address(data[:2]))
                            data = data[2:]
                    elif token == VARIABLE:
                        data = self._parse_variable(operands, data)
                    elif token == ADDR:
                        operands.append(self._make_address(data[:2]))
                        data = data[2:]
                    else:
                        size = int(token)
                        chunk, data = data[:size], data[size:]
                        operands.append(int.from_bytes(chunk, "little"))
                instructions.append(Instruction(consumed, opcode, operands))
                if opcode == 0x00 and not instructions[:-1]:
                    break
        except (AssertionError, KeyError, IndexError):
            log.warning("Salvaging over-read in script %#07x.", self.pointer)
            instructions = self._trim(instructions)
        return instructions

    def _parse_variable(self, operands: "list[Operand]", data: bytes) -> bytes:
        """Consume the ``0x14`` condition chain, appending structured operands; returns leftover data."""
        while True:
            code, data = data[0], data[1:]
            operands.append(code)
            if code == 0xFF:
                break
            if code & 0xF0 == 0xF0:  # monster-on-button / NPC-state
                operands.extend((data[0], data[1]))
                data = data[2:]
            elif code & 0xF0 == 0xC0:  # item owned exactly / at-least
                operands.append(int.from_bytes(data[:2], "little"))
                operands.append(int.from_bytes(data[2:4], "little"))
                data = data[4:]
            elif code & 0xF0 == 0x10:  # variable == / >=
                operands.extend((data[0], data[1]))
                data = data[2:]
            elif code & 0xE0 == 0x20:  # branch if true / false
                operands.append(self._make_address(data[:2]))
                data = data[2:]
            else:  # flag with AND / OR / NOT
                operands.append(data[0])
                data = data[1:]
        return data

    @staticmethod
    def _trim(instructions: list[Instruction]) -> list[Instruction]:
        """Cut a salvaged instruction list back to its last hard terminator."""
        for i in range(len(instructions) - 1, -1, -1):
            if instructions[i].opcode == 0x00:
                return instructions[: i + 1]
        return instructions

    def write(self) -> None:
        """Persist the script's bytes -- only if it was modified.

        - **Mode A (frozen):** an unmodified script is a **no-op**. Its bytes are already correct in the
          working ROM (a copy of the source), so re-writing them is pointless and, in a patch pipeline,
          would clobber any edits an earlier patch made to this region. Leaving frozen scripts untouched
          is what keeps ``write()`` confined to the scripts that actually changed.
        - **Mode B (dirty):** recompile in place at ``self.pointer`` and write. The write path is
          in-place only (no relocation), so the recompiled bytes must fit the original slot -- bounded by
          ``len(self.raw)`` (the next known pointer). Overrunning it would corrupt the following script,
          so raise instead.
        """
        if not self.dirty:
            return
        from structures.event_script.compiler import compile_script  # noqa: PLC0415

        data = compile_script(self, script_pointer=self.pointer)
        if len(data) > len(self.raw):
            msg = (
                f"Event script {self.pointer:#07x} (class {self.event_class.name}, index {self.index}) "
                f"compiled to {len(data)}B, exceeding its {len(self.raw)}B slot; the in-place write path "
                f"cannot relocate scripts."
            )
            raise ValueError(msg)
        write_file.seek(self.pointer)
        write_file.write(data)
