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

from iris.enums.event_scripts import EventClass
from iris.helpers.files import read_file, restore_pointer, write_file
from iris.logger import iris
from iris.structures.event_script.codec import PRE_DATA_SIZE, decode_text
from iris.structures.event_script.instructions import Address, Instruction
from iris.structures.event_script.opcodes import ADDR, POINTERS, TEXT, VARIABLE, operand_shape


if TYPE_CHECKING:
    from iris.structures.event_script.instructions import Operand


log = logging.getLogger(f"{iris.name}.EventScript")

# Fallback bound when no later pointer is known (mirrors terrorwave's END sentinels).
MAX_SCRIPT_LENGTH = 0x8000
END = 0x00
"""The END opcode, and the text code ``<END EVENT>``."""
STOP_LENGTH = 2
"""END bytes :meth:`EventScript.write` puts after a script that got shorter in place, so a reader stops there."""


class EventScript:
    """A single event script: opcode/operand instructions parsed from a contiguous byte range."""

    def __init__(self, base_pointer: int, offset: int, index: int, event_class: EventClass) -> None:
        log.debug(f"Creating EventScript {index=} {event_class.name} → pointer={base_pointer + offset:#08x}")
        self.base_pointer = base_pointer
        self.offset = offset
        self.pointer = base_pointer + offset
        self.index = index  # -1 == the NPC-load script
        self.event_class = event_class
        self.instructions: list[Instruction] = []
        self.raw = b""
        self.dirty = False
        self.jumped_into = False
        """Another script jumps into this one's bytes (FRUE shares code this way), so its layout must not change."""
        self._read = False
        self._pre = b""
        # The true physical room at `pointer` before the next known script, fixed at parse time.
        # Kept separate from `raw` (which write() below updates to the latest actual bytes) so a
        # second in-place write's budget doesn't shrink to whatever the *previous* write happened
        # to compile to -- it's always bounded by the real original slot.
        self._slot_size = 0
        self._used = 0
        """Bytes from ``pointer`` this script has ever filled: what a shorter rewrite pads, never the whole slot (a
        slot can run past the script into bytes that aren't its own)."""
        self._parsed_end = 0
        self.min_slot = 0
        """The size of this script's biggest version (``MapEvent.reserve``), 0 when it has none: the open-world extras
        replace some scripts with versions of other sizes, and the base ROM keeps room for the biggest."""
        self.slack = 0
        """Bytes a relocated container lays out after this script: :attr:`min_slot` less the size of the version it
        has now. Whatever later patches add to the script, it keeps the same slot whichever version it has."""

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
        self._slot_size = len(self.raw)
        self._pre = self._pre_data()
        self.instructions = self._parse(self.raw)
        self._used = self._parsed_end
        self._read = True

    def _make_address(self, data: bytes) -> Address:
        offset = int.from_bytes(data, "little")
        pointer = self.base_pointer + offset
        is_local = self.pointer <= pointer < self.pointer + len(self.raw)
        if is_local:
            return Address(offset - self.script_offset, is_local=True)
        return Address(offset, is_local=False)

    @property
    def external_jumps(self) -> list[Address]:
        """The jumps that leave this script (non-local addresses)."""
        return [
            operand
            for instruction in self.instructions
            for operand in instruction.operands
            if isinstance(operand, Address) and not operand.is_local
        ]

    def _parse(self, data: bytes) -> list[Instruction]:  # noqa: C901, PLR0912
        full = data
        instructions: list[Instruction] = []
        ends: list[int] = []
        try:
            while data:
                consumed = len(full) - len(data)
                if self._zero_tail(instructions, data, consumed):
                    break
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
                ends.append(len(full) - len(data))
                if opcode == 0x00 and not instructions[:-1]:
                    break
        except (AssertionError, KeyError, IndexError):
            log.warning("Salvaging over-read in script %#07x.", self.pointer)
            instructions = self._trim(instructions)
        self._parsed_end = ends[len(instructions) - 1] if instructions else 0
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
    def _zero_tail(instructions: list[Instruction], data: bytes, consumed: int) -> bool:
        """``data`` starts with the padding :meth:`write` leaves after a script that got shorter in place.

        True when the next byte is END, the last instruction ended the event, and no jump lands at or after it. Bytes
        after the padding can be what the old script's slot held past its last instruction, so they don't count. No
        vanilla or FRUE script has an END right after an END that nothing jumps past, so unpatched scripts parse as
        before.
        """
        if not instructions or data[0] != END:
            return False
        last = instructions[-1]
        ends = last.opcode == END or any(
            isinstance(operand, list) and operand and operand[-1].tag == END for operand in last.operands
        )
        jumps = (
            operand.offset
            for instruction in instructions
            for operand in instruction.operands
            if isinstance(operand, Address) and operand.is_local
        )
        return ends and all(offset < consumed for offset in jumps)

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
          ``len(self.raw)`` (the next known pointer). When they don't, the text is compressed again
          (``compile_script(compress=True)``); if that doesn't fit either, overrunning would corrupt the
          following script, so raise instead (``MapEvent.write`` relocates the container in that case).
        """
        if not self.dirty:
            return
        if self.jumped_into:
            msg = (
                f"Event script {self.pointer:#07x} (class {self.event_class.name}, index {self.index}) can't be "
                "rewritten: another script jumps into its bytes, and recompiling may move the target."
            )
            raise ValueError(msg)
        from iris.structures.event_script.compiler import compile_script  # noqa: PLC0415

        data = compile_script(self, script_pointer=self.pointer)
        if len(data) > self._slot_size:
            data = compile_script(self, script_pointer=self.pointer, compress=True)
        if len(data) > self._slot_size:
            msg = (
                f"Event script {self.pointer:#07x} (class {self.event_class.name}, index {self.index}) "
                f"compiled to {len(data)}B, exceeding its {self._slot_size}B slot; the in-place write path "
                f"cannot relocate scripts."
            )
            raise ValueError(msg)
        log.debug(f"Writing EventScript {self.index=} {self.event_class.name} ({len(data)}B) → {self.pointer=:#08x}")
        write_file.seek(self.pointer)
        write_file.write(data)
        # The old script's last bytes would parse as instructions (stray jumps included) next time the image is read.
        # An END after the end stops the reader (_zero_tail); two cover a script whose last instruction isn't END. The
        # rest stays: other scripts may copy text from it with <REPEAT>. One that copied from what was overwritten is
        # repaired by containers.repair_back_references.
        write_file.write(bytes([END]) * min(self._used - len(data), STOP_LENGTH))
        self._used = max(self._used, len(data))
        self.parse_written(data)

    def parse_written(self, data: bytes) -> None:
        """Take ``data``, just written at ``self.pointer``, as the script, and parse it again.

        Compiling changes byte offsets (text compressed again, a back-reference written out), so the instructions are
        parsed from the written bytes: their offsets then match the ROM, and so do the offsets callers derive from
        them (an item byte for a token, the next write's jump targets).
        """
        self.raw = data
        self._pre = self._pre_data()
        self.instructions = self._parse(data)
        self.dirty = False
