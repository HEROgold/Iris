"""
Event Script System Redesign Implementation
==========================================

This module implements a redesigned event script system for the Lufia II randomizer
that integrates with the existing Zone and MapEvent infrastructure.
"""

import re
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from structures.zone import Zone


# =============================================================================
# Core Data Structures
# =============================================================================

@dataclass
class MemoryBlock:
    """Represents an allocated block of memory in ROM."""
    address: int
    size: int
    region: str

    @property
    def end_address(self) -> int:
        return self.address + self.size - 1


@dataclass
class ScriptMetadata:
    """Metadata associated with a script."""
    signature: str
    map_index: int
    event_list: str
    script_index: int | None
    is_npc_loader: bool


class ConditionType(Enum):
    """Types of conditions in conditional instructions."""
    FLAG_SET = "flag_set"
    FLAG_NOT_SET = "flag_not_set"
    ITEM_EXACT = "item_exact"
    ITEM_MINIMUM = "item_minimum"
    VARIABLE_EQUAL = "variable_equal"
    VARIABLE_GTE = "variable_gte"


@dataclass
class Condition:
    """Represents a condition in conditional logic."""
    type: ConditionType
    parameter1: int
    parameter2: int | None = None

    def __str__(self) -> str:
        if self.type == ConditionType.FLAG_SET:
            return f"Flag {self.parameter1:02X} set"
        if self.type == ConditionType.ITEM_MINIMUM:
            return f"Item {self.parameter1:03X} >= {self.parameter2}"
        return None
        # ... other condition types


# =============================================================================
# Exception Hierarchy
# =============================================================================

class EventScriptError(Exception):
    """Base exception for event script errors."""
    def __init__(self, message: str, context: dict | None = None) -> None:
        super().__init__(message)
        self.context = context or {}


class ParseError(EventScriptError):
    """Error during script parsing."""
    def __init__(self, position: int, instruction: int, message: str) -> None:
        context = {"position": position, "instruction": f"0x{instruction:02X}"}
        super().__init__(f"Parse error at {position}: {message}", context)


class ValidationError(EventScriptError):
    """Error during script validation."""
    def __init__(self, errors: list[str], script_signature: str) -> None:
        context = {"script": script_signature, "error_count": len(errors)}
        message = f"Validation failed for {script_signature}: {len(errors)} errors"
        super().__init__(message, context)


class MemoryError(EventScriptError):
    """Error during memory allocation."""
    def __init__(self, requested_size: int, available_size: int) -> None:
        context = {"requested": requested_size, "available": available_size}
        super().__init__(f"Insufficient memory: need {requested_size}, have {available_size}", context)


class UnknownInstructionError(EventScriptError):
    """Error for unknown instruction opcodes."""


# =============================================================================
# Command Pattern: Event Instructions
# =============================================================================

class EventInstruction(ABC):
    """Abstract base class for all event instructions."""

    def __init__(self, opcode: int, parameters: list[Any] | None = None) -> None:
        self.opcode = opcode
        self.parameters = parameters or []
        self.line_number: int | None = None

    @abstractmethod
    def parse_parameters(self, data: bytes) -> tuple[list[Any], bytes]:
        """Parse parameters from binary data."""

    @abstractmethod
    def compile_parameters(self) -> bytes:
        """Compile parameters to binary data."""

    @abstractmethod
    def validate(self) -> list[str]:
        """Validate instruction parameters. Returns list of error messages."""

    @abstractmethod
    def to_pretty_string(self) -> str:
        """Convert instruction to human-readable format."""

    @classmethod
    @abstractmethod
    def from_pretty_string(cls, line: str) -> "EventInstruction":
        """Create instruction from human-readable format."""

    def __str__(self) -> str:
        return self.to_pretty_string()


class EndEventInstruction(EventInstruction):
    """Instruction to end an event (opcode 0x00)."""

    def __init__(self) -> None:
        super().__init__(0x00, [])

    def parse_parameters(self, data: bytes) -> tuple[list[Any], bytes]:
        return [], data

    def compile_parameters(self) -> bytes:
        return b""

    def validate(self) -> list[str]:
        return []  # Always valid

    def to_pretty_string(self) -> str:
        return "00()"

    @classmethod
    def from_pretty_string(cls, line: str) -> "EndEventInstruction":
        if not re.match(r"00\(\)", line.strip()):
            raise ParseError(0, 0, f"Invalid end event format: {line}")
        return cls()


class TextInstruction(EventInstruction):
    """Instruction to display text (opcode 0x13)."""

    def __init__(self, speaker_id: int | None = None, text: str = "") -> None:
        super().__init__(0x13)
        self.speaker_id = speaker_id
        self.text = text

    def parse_parameters(self, data: bytes) -> tuple[list[Any], bytes]:
        # Simplified parsing - in real implementation would handle full text format
        text_data: list[int] = []
        remaining = data

        # Parse text until terminator
        while remaining and remaining[0] not in {0x00, 0x01}:
            text_data.append(remaining[0])
            remaining = remaining[1:]

        if remaining:
            text_data.append(remaining[0])  # Include terminator
            remaining = remaining[1:]

        self.parameters = [("text", bytes(text_data))]
        return self.parameters, remaining

    def compile_parameters(self) -> bytes:
        # Simplified compilation
        if self.speaker_id is not None:
            result = bytes([0x09])  # VOICE tag
            result += bytes([self.speaker_id])
        else:
            result = b""

        # Convert text to bytes (simplified)
        text_bytes = self.text.encode("ascii", errors="ignore")
        result += text_bytes
        result += bytes([0x01])  # END MESSAGE

        return result

    def validate(self) -> list[str]:
        errors = []
        if self.speaker_id is not None and not (0 <= self.speaker_id <= 255):
            errors.append(f"Invalid speaker ID: {self.speaker_id}")
        if len(self.text) > 200:  # Arbitrary limit
            errors.append("Text too long")
        return errors

    def to_pretty_string(self) -> str:
        if self.speaker_id is not None:
            return f"13: <VOICE {self.speaker_id:02X}>{self.text}<END MESSAGE>"
        return f"13: {self.text}<END MESSAGE>"

    @classmethod
    def from_pretty_string(cls, line: str) -> "TextInstruction":
        # Parse format: "13: <VOICE XX>text<END MESSAGE>" or "13: text<END MESSAGE>"
        voice_match = re.search(r"<VOICE ([0-9A-Fa-f]{2})>", line)
        speaker_id = int(voice_match.group(1), 16) if voice_match else None

        # Extract text between voice tag and end message
        text_start = voice_match.end() if voice_match else line.find(":") + 1

        text_end = line.find("<END MESSAGE>")
        if text_end == -1:
            raise ParseError(0, 0x13, "Missing <END MESSAGE> tag")

        text = line[text_start:text_end].strip()
        return cls(speaker_id, text)


class ConditionalInstruction(EventInstruction):
    """Instruction for conditional branching (opcode 0x14)."""

    def __init__(self, conditions: list[Condition] | None = None, target_label: str = "") -> None:
        super().__init__(0x14)
        self.conditions = conditions or []
        self.target_label = target_label
        self.branch_if_true = True

    def parse_parameters(self, data: bytes) -> tuple[list[Any], bytes]:
        # Simplified parsing of conditional logic
        remaining = data

        while remaining and remaining[0] != 0xFF:
            condition_type = remaining[0]

            if condition_type in {0x00, 0x01}:  # Flag conditions
                flag_id = remaining[1]
                condition = Condition(
                    ConditionType.FLAG_SET if condition_type == 0x00 else ConditionType.FLAG_NOT_SET,
                    flag_id,
                )
                self.conditions.append(condition)
                remaining = remaining[2:]
            elif condition_type in {0xC0, 0xC2}:  # Item conditions
                item_id = int.from_bytes(remaining[1:3], byteorder="little")
                quantity = int.from_bytes(remaining[3:5], byteorder="little")
                condition = Condition(
                    ConditionType.ITEM_EXACT if condition_type == 0xC0 else ConditionType.ITEM_MINIMUM,
                    item_id,
                    quantity,
                )
                self.conditions.append(condition)
                remaining = remaining[5:]
            else:
                break

        # Skip terminator and get target
        if remaining and remaining[0] == 0xFF:
            remaining = remaining[1:]

        self.parameters = ["conditions", *self.conditions]
        return self.parameters, remaining

    def compile_parameters(self) -> bytes:
        result = b""

        for condition in self.conditions:
            if condition.type in {ConditionType.FLAG_SET, ConditionType.FLAG_NOT_SET}:
                result += bytes([0x00 if condition.type == ConditionType.FLAG_SET else 0x01])
                result += bytes([condition.parameter1])
            elif condition.type in {ConditionType.ITEM_EXACT, ConditionType.ITEM_MINIMUM}:
                result += bytes([0xC0 if condition.type == ConditionType.ITEM_EXACT else 0xC2])
                result += condition.parameter1.to_bytes(2, byteorder="little")
                result += condition.parameter2.to_bytes(2, byteorder="little")

        result += bytes([0x20 if self.branch_if_true else 0x30])  # Branch type
        result += bytes([0xFF])  # Terminator

        return result

    def validate(self) -> list[str]:
        errors = []
        if not self.conditions:
            errors.append("Conditional instruction has no conditions")
        if not self.target_label:
            errors.append("Conditional instruction has no target")
        return errors

    def to_pretty_string(self) -> str:
        condition_str = " AND ".join(str(c) for c in self.conditions)
        branch_type = "if" if self.branch_if_true else "unless"
        return f"14({condition_str}) {branch_type} jump to @{self.target_label}"

    @classmethod
    def from_pretty_string(cls, line: str) -> "ConditionalInstruction":
        # Simplified parsing - real implementation would be more complex
        match = re.search(r"14\((.*?)\)", line)
        if not match:
            raise ParseError(0, 0x14, f"Invalid conditional format: {line}")

        # For now, create empty conditional
        return cls()


class ItemInstruction(EventInstruction):
    """Instruction to give items (opcodes 0x20, 0x21)."""

    def __init__(self, item_id: int, quantity: int = 1, high_range: bool = False) -> None:
        opcode = 0x21 if high_range else 0x20
        super().__init__(opcode)
        self.item_id = item_id
        self.quantity = quantity
        self.high_range = high_range

    def parse_parameters(self, data: bytes) -> tuple[list[Any], bytes]:
        if len(data) < 2:
            raise ParseError(0, self.opcode, "Insufficient data for item instruction")

        self.item_id = data[0]
        self.quantity = data[1]
        self.parameters = [self.item_id, self.quantity]

        return self.parameters, data[2:]

    def compile_parameters(self) -> bytes:
        return bytes([self.item_id, self.quantity])

    def validate(self) -> list[str]:
        errors = []
        if not (0 <= self.item_id <= 255):
            errors.append(f"Invalid item ID: {self.item_id}")
        if not (1 <= self.quantity <= 255):
            errors.append(f"Invalid quantity: {self.quantity}")
        return errors

    def to_pretty_string(self) -> str:
        return f"{self.opcode:02X}({self.item_id:02X}-{self.quantity:02X})"

    @classmethod
    def from_pretty_string(cls, line: str) -> "ItemInstruction":
        match = re.match(r"(20|21)\(([0-9A-Fa-f]{2})-([0-9A-Fa-f]{2})\)", line.strip())
        if not match:
            raise ParseError(0, 0x20, f"Invalid item instruction format: {line}")

        opcode = int(match.group(1), 16)
        item_id = int(match.group(2), 16)
        quantity = int(match.group(3), 16)
        high_range = (opcode == 0x21)

        return cls(item_id, quantity, high_range)


# =============================================================================
# Factory Pattern: Instruction Creation
# =============================================================================

class InstructionFactory:
    """Factory for creating event instructions."""

    _registry: dict[int, type[EventInstruction]] = {}

    @classmethod
    def register(cls, opcode: int, instruction_class: type[EventInstruction]) -> None:
        """Register an instruction class for a specific opcode."""
        cls._registry[opcode] = instruction_class

    @classmethod
    def create(cls, opcode: int, parameters: list[Any] | None = None) -> EventInstruction:
        """Create an instruction instance for the given opcode."""
        if opcode not in cls._registry:
            msg = f"Unknown opcode: {opcode:02X}"
            raise UnknownInstructionError(msg)

        instruction_class = cls._registry[opcode]
        # For now, create with default parameters - real implementation would use parameters
        return instruction_class()

    @classmethod
    def create_from_data(cls, opcode: int, data: bytes) -> tuple[EventInstruction, bytes]:
        """Create an instruction by parsing binary data."""
        instruction = cls.create(opcode)
        parameters, remaining = instruction.parse_parameters(data)
        return instruction, remaining

    @classmethod
    def create_from_string(cls, line: str) -> EventInstruction:
        """Create an instruction from human-readable format."""
        # Extract opcode from line
        match = re.match(r"([0-9A-Fa-f]{2})", line.strip())
        if not match:
            raise ParseError(0, 0, f"Cannot extract opcode from line: {line}")

        opcode = int(match.group(1), 16)
        if opcode not in cls._registry:
            msg = f"Unknown opcode: {opcode:02X}"
            raise UnknownInstructionError(msg)

        instruction_class = cls._registry[opcode]
        return instruction_class.from_pretty_string(line)


# Register instruction types
InstructionFactory.register(0x00, EndEventInstruction)
InstructionFactory.register(0x13, TextInstruction)
InstructionFactory.register(0x14, ConditionalInstruction)
InstructionFactory.register(0x20, ItemInstruction)
InstructionFactory.register(0x21, ItemInstruction)


# =============================================================================
# Strategy Pattern: Text Processing
# =============================================================================

class TextProcessor(ABC):
    """Abstract base class for text processing strategies."""

    @abstractmethod
    def encode(self, text: str) -> bytes:
        """Encode text string to bytes."""

    @abstractmethod
    def decode(self, data: bytes) -> str:
        """Decode bytes to text string."""


class PlainTextProcessor(TextProcessor):
    """Simple text processor without compression."""

    CHARACTER_MAP = {
        0x00: "<END EVENT>",
        0x01: "<END MESSAGE>",
        0x03: "\n",
        0x04: "<PAUSE>",
        0x09: "$MAXIM$",
    }

    REVERSE_CHARACTER_MAP = {v: k for k, v in CHARACTER_MAP.items()}

    def encode(self, text: str) -> bytes:
        """Encode text to bytes using character mapping."""
        result = b""
        i = 0
        while i < len(text):
            # Look for special tags
            found_tag = False
            for tag, byte_val in self.REVERSE_CHARACTER_MAP.items():
                if text[i:].startswith(tag):
                    result += bytes([byte_val])
                    i += len(tag)
                    found_tag = True
                    break

            if not found_tag:
                # Regular character
                result += bytes([ord(text[i])])
                i += 1

        return result

    def decode(self, data: bytes) -> str:
        """Decode bytes to text using character mapping."""
        result = ""
        for byte_val in data:
            if byte_val in self.CHARACTER_MAP:
                result += self.CHARACTER_MAP[byte_val]
            else:
                result += chr(byte_val) if 32 <= byte_val <= 126 else f"<{byte_val:02X}>"

        return result


class CompressedTextProcessor(PlainTextProcessor):
    """Text processor with compression support."""

    def __init__(self) -> None:
        self.compression_buffer = ""

    def encode(self, text: str) -> bytes:
        """Encode text with compression."""
        # For now, just use plain encoding
        # Real implementation would add compression logic
        return super().encode(text)

    def decode(self, data: bytes) -> str:
        """Decode compressed text."""
        # For now, just use plain decoding
        # Real implementation would handle compression
        return super().decode(data)


# =============================================================================
# Builder Pattern: Script Construction
# =============================================================================

class ScriptBuilder:
    """Builder for constructing event scripts with a fluent interface."""

    def __init__(self) -> None:
        self._instructions: list[EventInstruction] = []
        self._labels: dict[str, int] = {}
        self._metadata: ScriptMetadata = None
        self._current_line = 0

    def add_instruction(self, instruction: EventInstruction, line_number: int | None = None) -> "ScriptBuilder":
        """Add an instruction to the script."""
        if line_number is not None:
            self._current_line = line_number
        else:
            self._current_line += 10  # Default increment

        instruction.line_number = self._current_line
        self._instructions.append(instruction)
        return self

    def add_text(self, speaker: int, message: str, line_number: int | None = None) -> "ScriptBuilder":
        """Add a text instruction."""
        instruction = TextInstruction(speaker, message)
        return self.add_instruction(instruction, line_number)

    def add_item(self, item_id: int, quantity: int = 1, line_number: int | None = None) -> "ScriptBuilder":
        """Add an item instruction."""
        high_range = item_id > 255
        if high_range:
            item_id -= 256
        instruction = ItemInstruction(item_id, quantity, high_range)
        return self.add_instruction(instruction, line_number)

    def add_conditional(self, conditions: list[Condition], target: str,
                       branch_if_true: bool = True, line_number: int | None = None) -> "ScriptBuilder":
        """Add a conditional instruction."""
        instruction = ConditionalInstruction(conditions, target)
        instruction.branch_if_true = branch_if_true
        return self.add_instruction(instruction, line_number)

    def add_label(self, name: str) -> "ScriptBuilder":
        """Add a label at the current position."""
        self._labels[name] = self._current_line
        return self

    def add_end(self, line_number: int | None = None) -> "ScriptBuilder":
        """Add an end event instruction."""
        instruction = EndEventInstruction()
        return self.add_instruction(instruction, line_number)

    def set_metadata(self, signature: str, map_index: int, event_list: str,
                    script_index: int | None = None, is_npc_loader: bool = False) -> "ScriptBuilder":
        """Set script metadata."""
        self._metadata = ScriptMetadata(signature, map_index, event_list, script_index, is_npc_loader)
        return self

    def build(self) -> "Script":
        """Build the final script."""
        if not self._metadata:
            msg = "Script metadata must be set before building"
            raise ValueError(msg)

        return Script(self._instructions, self._labels, self._metadata)


# =============================================================================
# Core Script Class
# =============================================================================

class Script:
    """Represents a complete event script."""

    def __init__(self, instructions: list[EventInstruction],
                 labels: dict[str, int], metadata: ScriptMetadata) -> None:
        self.instructions = instructions
        self.labels = labels
        self.metadata = metadata
        self._cached_size: int | None = None

    @property
    def size(self) -> int:
        """Calculate the compiled size of the script."""
        if self._cached_size is None:
            total = 0
            for instruction in self.instructions:
                total += 1  # Opcode byte
                total += len(instruction.compile_parameters())
            self._cached_size = total
        return self._cached_size

    def accept(self, visitor: "ScriptVisitor"):
        """Accept a visitor for processing."""
        return visitor.visit_script(self)

    def get_instruction_at_line(self, line_number: int) -> EventInstruction | None:
        """Get the instruction at a specific line number."""
        for instruction in self.instructions:
            if instruction.line_number == line_number:
                return instruction
        return None

    def __str__(self) -> str:
        """String representation of the script."""
        lines = [f"EVENT {self.metadata.signature}"]
        for instruction in self.instructions:
            line_num = instruction.line_number or 0
            lines.append(f"  {line_num:04X}. {instruction}")
        return "\n".join(lines)


# =============================================================================
# Visitor Pattern: Script Processing
# =============================================================================

class ScriptVisitor(ABC):
    """Abstract base class for script visitors."""

    @abstractmethod
    def visit_script(self, script: Script):
        """Visit a script."""

    def visit_instruction(self, instruction: EventInstruction) -> None:
        """Visit an instruction - default implementation calls specific methods."""
        method_name = f"visit_{instruction.__class__.__name__.lower()}"
        if hasattr(self, method_name):
            getattr(self, method_name)(instruction)
        else:
            self.visit_generic_instruction(instruction)

    def visit_generic_instruction(self, instruction: EventInstruction) -> None:
        """Default handler for instructions without specific visitors."""


class ValidationVisitor(ScriptVisitor):
    """Visitor for validating scripts."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def visit_script(self, script: Script):
        """Validate an entire script."""
        self.errors.clear()
        self.warnings.clear()

        # Validate metadata
        if not script.metadata.signature:
            self.errors.append("Script has no signature")

        # Validate instructions
        for instruction in script.instructions:
            self.visit_instruction(instruction)

            # Validate instruction-specific errors
            instruction_errors = instruction.validate()
            self.errors.extend(instruction_errors)

        # Check for proper termination
        if not script.instructions or not isinstance(script.instructions[-1], EndEventInstruction):
            self.errors.append("Script does not end with EndEventInstruction")

        # Validate label references
        self._validate_label_references(script)

        return len(self.errors) == 0

    def _validate_label_references(self, script: Script) -> None:
        """Validate that all label references point to valid labels."""
        for instruction in script.instructions:
            if isinstance(instruction, ConditionalInstruction):
                if instruction.target_label and instruction.target_label not in script.labels:
                    self.errors.append(f"Undefined label: {instruction.target_label}")


class CompilationVisitor(ScriptVisitor):
    """Visitor for compiling scripts to bytecode."""

    def __init__(self) -> None:
        self.bytecode = bytearray()
        self.address_map: dict[int, int] = {}  # line_number -> bytecode_offset

    def visit_script(self, script: Script) -> bytes:
        """Compile a script to bytecode."""
        self.bytecode.clear()
        self.address_map.clear()

        for instruction in script.instructions:
            if instruction.line_number is not None:
                self.address_map[instruction.line_number] = len(self.bytecode)

            # Add opcode
            self.bytecode.append(instruction.opcode)

            # Add parameters
            param_data = instruction.compile_parameters()
            self.bytecode.extend(param_data)

        return bytes(self.bytecode)


class OptimizationVisitor(ScriptVisitor):
    """Visitor for optimizing scripts."""

    def __init__(self) -> None:
        self.optimized_instructions: list[EventInstruction] = []

    def visit_script(self, script: Script) -> list[EventInstruction]:
        """Optimize a script's instructions."""
        self.optimized_instructions.clear()

        prev_instruction = None
        for instruction in script.instructions:
            # Example optimization: remove consecutive pause instructions
            if (isinstance(instruction, EndEventInstruction) and
                isinstance(prev_instruction, EndEventInstruction)):
                continue  # Skip duplicate end instructions

            self.optimized_instructions.append(instruction)
            prev_instruction = instruction

        return self.optimized_instructions


# =============================================================================
# Memory Management
# =============================================================================

class MemoryPool(ABC):
    """Abstract base class for memory pools."""

    @abstractmethod
    def allocate(self, size: int) -> MemoryBlock:
        """Allocate a block of memory."""

    @abstractmethod
    def deallocate(self, block: MemoryBlock):
        """Deallocate a block of memory."""

    @abstractmethod
    def can_allocate(self, size: int) -> bool:
        """Check if allocation of given size is possible."""


class BankAwareMemoryPool(MemoryPool):
    """Memory pool that respects SNES bank boundaries."""

    def __init__(self, base_address: int, bank_size: int = 0x8000, region: str = "") -> None:
        self.base_address = base_address
        self.bank_size = bank_size
        self.region = region
        self.free_blocks: list[tuple[int, int]] = [(base_address, base_address + bank_size)]
        self.allocated_blocks: list[MemoryBlock] = []

    def allocate(self, size: int) -> MemoryBlock:
        """Allocate memory ensuring it doesn't cross bank boundaries."""
        for i, (start, end) in enumerate(self.free_blocks):
            # Check if block fits and doesn't cross bank boundary
            if end - start >= size:
                block_end = start + size
                if (start & 0xFF8000) == ((block_end - 1) & 0xFF8000):
                    # Allocation fits within bank
                    block = MemoryBlock(start, size, self.region)
                    self.allocated_blocks.append(block)

                    # Update free blocks
                    if end - block_end > 0:
                        self.free_blocks[i] = (block_end, end)
                    else:
                        del self.free_blocks[i]

                    return block

        # No suitable block found
        raise MemoryError(size, max(end - start for start, end in self.free_blocks) if self.free_blocks else 0)

    def deallocate(self, block: MemoryBlock) -> None:
        """Deallocate a memory block."""
        if block in self.allocated_blocks:
            self.allocated_blocks.remove(block)
            self.free_blocks.append((block.address, block.address + block.size))
            self._merge_free_blocks()

    def can_allocate(self, size: int) -> bool:
        """Check if allocation is possible."""
        try:
            # Simulate allocation
            for start, end in self.free_blocks:
                if end - start >= size:
                    block_end = start + size
                    if (start & 0xFF8000) == ((block_end - 1) & 0xFF8000):
                        return True
            return False
        except:
            return False

    def _merge_free_blocks(self) -> None:
        """Merge adjacent free blocks."""
        self.free_blocks.sort()
        merged = []
        for start, end in self.free_blocks:
            if merged and merged[-1][1] == start:
                merged[-1] = (merged[-1][0], end)
            else:
                merged.append((start, end))
        self.free_blocks = merged


class ScriptMemoryManager:
    """Manager for script memory allocation."""

    def __init__(self) -> None:
        self.npc_pool = BankAwareMemoryPool(0x38000, region="npc_loader")
        self.event_pool = BankAwareMemoryPool(0x3A000, region="events")

    def allocate_script(self, script: Script) -> MemoryBlock:
        """Allocate memory for a script."""
        pool = self.npc_pool if script.metadata.is_npc_loader else self.event_pool
        return pool.allocate(script.size)

    def deallocate_script(self, block: MemoryBlock) -> None:
        """Deallocate script memory."""
        if block.region == "npc_loader":
            self.npc_pool.deallocate(block)
        else:
            self.event_pool.deallocate(block)


# =============================================================================
# Template Method Pattern: Script Processing Pipeline
# =============================================================================

class ScriptProcessor:
    """Template method for processing scripts."""

    def __init__(self, config: "EventSystemConfig" = None) -> None:
        self.config = config or EventSystemConfig()
        self.text_processor = self.config.text_processor()
        self.memory_manager = ScriptMemoryManager()

    def process_from_data(self, raw_data: bytes, metadata: ScriptMetadata) -> "CompiledScript":
        """Template method for processing scripts from binary data."""
        parsed = self.parse(raw_data, metadata)
        validated = self.validate(parsed)
        optimized = self.optimize(validated)
        return self.compile(optimized)

    def process_from_text(self, text: str, metadata: ScriptMetadata) -> "CompiledScript":
        """Template method for processing scripts from text."""
        parsed = self.parse_text(text, metadata)
        validated = self.validate(parsed)
        optimized = self.optimize(validated)
        return self.compile(optimized)

    def parse(self, data: bytes, metadata: ScriptMetadata) -> Script:
        """Parse binary data into a script."""
        instructions = []
        labels = {}
        remaining = data
        line_number = 0

        while remaining:
            opcode = remaining[0]
            remaining = remaining[1:]

            try:
                instruction, remaining = InstructionFactory.create_from_data(opcode, remaining)
                instruction.line_number = line_number
                instructions.append(instruction)
                line_number += 10

                # Stop at end instruction
                if isinstance(instruction, EndEventInstruction):
                    break

            except UnknownInstructionError:
                # Skip unknown instruction
                remaining = remaining[1:] if remaining else b""

        return Script(instructions, labels, metadata)

    def parse_text(self, text: str, metadata: ScriptMetadata) -> Script:
        """Parse text format into a script."""
        builder = ScriptBuilder().set_metadata(
            metadata.signature, metadata.map_index,
            metadata.event_list, metadata.script_index, metadata.is_npc_loader,
        )

        for line in text.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Extract line number
            line_match = re.match(r"([0-9A-Fa-f]{4})\.\s*(.+)", line)
            if line_match:
                line_number = int(line_match.group(1), 16)
                instruction_text = line_match.group(2)

                try:
                    instruction = InstructionFactory.create_from_string(instruction_text)
                    builder.add_instruction(instruction, line_number)
                except (ParseError, UnknownInstructionError):
                    # Skip invalid instructions
                    pass

        return builder.build()

    def validate(self, script: Script) -> Script:
        """Validate a script."""
        validator = ValidationVisitor()
        is_valid = validator.visit_script(script)

        if not is_valid and self.config.validation_strict:
            raise ValidationError(validator.errors, script.metadata.signature)

        return script

    def optimize(self, script: Script) -> Script:
        """Optimize a script."""
        if self.config.optimization_level > 0:
            optimizer = OptimizationVisitor()
            optimized_instructions = optimizer.visit_script(script)
            return Script(optimized_instructions, script.labels, script.metadata)

        return script

    def compile(self, script: Script) -> "CompiledScript":
        """Compile a script to bytecode."""
        compiler = CompilationVisitor()
        bytecode = compiler.visit_script(script)
        memory_block = self.memory_manager.allocate_script(script)

        return CompiledScript(script, bytecode, memory_block)


# =============================================================================
# Configuration
# =============================================================================

class EventSystemConfig:
    """Configuration for the event system."""

    def __init__(self) -> None:
        self.text_processor: type[TextProcessor] = CompressedTextProcessor
        self.optimization_level: int = 2
        self.validation_strict: bool = True
        self.memory_banks: dict[str, int] = {
            "npc_loader": 0x38000,
            "events": 0x3A000,
        }
        self.instruction_set: str = "lufia2_na"

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> "EventSystemConfig":
        """Create configuration from dictionary."""
        config = cls()
        for key, value in config_dict.items():
            if hasattr(config, key):
                setattr(config, key, value)
        return config


# =============================================================================
# Compiled Script
# =============================================================================

class CompiledScript:
    """Represents a compiled script with bytecode and memory allocation."""

    def __init__(self, original_script: Script, bytecode: bytes, memory_block: MemoryBlock) -> None:
        self.original_script = original_script
        self.bytecode = bytecode
        self.memory_block = memory_block

    @property
    def size(self) -> int:
        """Size of the compiled bytecode."""
        return len(self.bytecode)

    @property
    def address(self) -> int:
        """Memory address where script is allocated."""
        return self.memory_block.address

    def __str__(self) -> str:
        return f"CompiledScript({self.original_script.metadata.signature}, {self.size} bytes @ 0x{self.address:X})"


# =============================================================================
# Main Event System
# =============================================================================

class EventSystem:
    """Main event system coordinating all components."""

    def __init__(self, config: EventSystemConfig = None) -> None:
        self.config = config or EventSystemConfig()
        self.processor = ScriptProcessor(self.config)
        self.compiled_scripts: dict[str, CompiledScript] = {}

    def load_script_from_data(self, data: bytes, signature: str,
                             map_index: int, event_list: str,
                             script_index: int | None = None,
                             is_npc_loader: bool = False) -> CompiledScript:
        """Load and compile a script from binary data."""
        metadata = ScriptMetadata(signature, map_index, event_list, script_index, is_npc_loader)
        compiled = self.processor.process_from_data(data, metadata)
        self.compiled_scripts[signature] = compiled
        return compiled

    def load_script_from_text(self, text: str, signature: str,
                             map_index: int, event_list: str,
                             script_index: int | None = None,
                             is_npc_loader: bool = False) -> CompiledScript:
        """Load and compile a script from text format."""
        metadata = ScriptMetadata(signature, map_index, event_list, script_index, is_npc_loader)
        compiled = self.processor.process_from_text(text, metadata)
        self.compiled_scripts[signature] = compiled
        return compiled

    def get_script(self, signature: str) -> CompiledScript | None:
        """Get a compiled script by signature."""
        return self.compiled_scripts.get(signature)

    def create_script_builder(self) -> ScriptBuilder:
        """Create a new script builder."""
        return ScriptBuilder()

    def export_all_scripts(self) -> str:
        """Export all scripts to text format."""
        lines: list[str] = []
        for _signature, compiled in sorted(self.compiled_scripts.items()):
            lines.append(str(compiled.original_script))
            lines.append("")  # Empty line between scripts
        return "\n".join(lines)


# =============================================================================
# Integration with Existing System
# =============================================================================

class LufiaEventSystem:
    """Integration layer for the Lufia II event system with existing Zone/MapEvent classes."""

    def __init__(self, config: EventSystemConfig = None) -> None:
        self.config = config or EventSystemConfig()
        self.processor = ScriptProcessor(self.config)
        self.compiled_scripts: dict[str, CompiledScript] = {}
        self._zone_scripts: dict[int, list[CompiledScript]] = defaultdict(list)

    def load_zone_events(self, zone: "Zone") -> list[CompiledScript]:
        """Load all event scripts for a given zone."""
        if zone.index in self._zone_scripts:
            return self._zone_scripts[zone.index]

        compiled_scripts = []

        # Load NPC loader script (X class)
        npc_script = self._load_npc_script(zone)
        if npc_script:
            compiled_scripts.append(npc_script)

        # Load event lists (A, B, C, D classes)
        for event_list in zone.event._event_lists:
            for event_script in event_list._events:
                compiled = self._load_event_script(event_script, zone)
                if compiled:
                    compiled_scripts.append(compiled)

        self._zone_scripts[zone.index] = compiled_scripts
        return compiled_scripts

    def _load_npc_script(self, zone: "Zone") -> CompiledScript | None:
        """Load the NPC loader script (X class) for a zone."""
        try:
            from helpers.files import read_file

            # Read NPC script data
            read_file.seek(zone.event.npc_pointer)
            script_data = self._read_script_data(zone.event.npc_pointer)

            # Create metadata
            signature = f"{zone.index:02X}-X-00"
            metadata = ScriptMetadata(
                signature=signature,
                map_index=zone.index,
                event_list="X",
                script_index=0,
                is_npc_loader=True,
            )

            # Process script
            compiled = self.processor.process_from_data(script_data, metadata)
            self.compiled_scripts[signature] = compiled
            return compiled

        except Exception:
            return None

    def _load_event_script(self, event_script, zone: "Zone") -> CompiledScript | None:
        """Load an individual event script."""
        try:
            from helpers.files import read_file

            # Read script data
            read_file.seek(event_script.pointer)
            script_data = self._read_script_data(event_script.pointer)

            # Determine event class and index
            event_class = self._determine_event_class(event_script)
            script_index = self._determine_script_index(event_script)

            # Create metadata
            signature = f"{zone.index:02X}-{event_class}-{script_index:02X}"
            metadata = ScriptMetadata(
                signature=signature,
                map_index=zone.index,
                event_list=event_class,
                script_index=script_index,
                is_npc_loader=False,
            )

            # Process script
            compiled = self.processor.process_from_data(script_data, metadata)
            self.compiled_scripts[signature] = compiled
            return compiled

        except Exception:
            return None

    def _read_script_data(self, pointer: int) -> bytes:
        """Read script data from pointer until END instruction."""
        from helpers.files import read_file

        read_file.seek(pointer)
        data = bytearray()

        while True:
            opcode = read_file.read(1)
            if not opcode:
                break

            data.extend(opcode)
            opcode_val = opcode[0]

            # Get parameter count for this opcode
            param_count = self._get_opcode_params(opcode_val)
            if param_count > 0:
                params = read_file.read(param_count)
                data.extend(params)

            # Handle special cases
            if opcode_val == 0x00:  # END
                break
            if opcode_val in [0x08, 0x13, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67]:
                # Text mode - read until text terminator
                text_data = self._read_text_data()
                data.extend(text_data)
            elif opcode_val == 0x14:  # Conditional
                cond_data = self._read_conditional_data()
                data.extend(cond_data)

        return bytes(data)

    def _read_text_data(self) -> bytes:
        """Read text data until terminator."""
        from helpers.files import read_file

        data = bytearray()
        while True:
            byte = read_file.read(1)
            if not byte:
                break
            data.extend(byte)
            if byte[0] in [0x00, 0x01]:  # Text terminators
                break
        return bytes(data)

    def _read_conditional_data(self) -> bytes:
        """Read conditional instruction data until 0xFF terminator."""
        from helpers.files import read_file

        data = bytearray()
        while True:
            byte = read_file.read(1)
            if not byte:
                break
            data.extend(byte)

            flag = byte[0]
            if flag == 0xFF:
                break

            # Read additional parameters based on flag type
            if flag & 0xF0 == 0xC0:  # Item conditions
                data.extend(read_file.read(4))  # item_id (2) + quantity (2)
            elif flag & 0xF0 == 0x10:  # Variable conditions
                data.extend(read_file.read(2))  # variable + value
            elif flag & 0xE0 in [0x20, 0x30]:  # Branch conditions
                data.extend(read_file.read(2))  # branch offset
            else:  # Flag conditions
                data.extend(read_file.read(1))  # flag number

        return bytes(data)

    def _get_opcode_params(self, opcode: int) -> int:
        """Get parameter count for opcode from documentation."""
        # Based on the opcode table from events.py
        opcode_params = {
            0x00: 0, 0x01: 2, 0x02: 2, 0x03: 2, 0x04: 2, 0x05: 2, 0x06: 2, 0x07: 1,
            0x08: 0, 0x09: 0, 0x0A: 2, 0x0B: 0, 0x0C: 0, 0x0D: 0, 0x0E: 0, 0x0F: 0,
            0x10: 1, 0x11: 0, 0x12: 2, 0x13: 1, 0x14: 1, 0x15: 3, 0x16: 3, 0x17: 1,
            0x18: 1, 0x19: 0, 0x1A: 1, 0x1B: 1, 0x1C: 2, 0x1D: 2, 0x1E: 2, 0x1F: 2,
            0x20: 2, 0x21: 2, 0x22: 2, 0x23: 2, 0x24: 2, 0x25: 2, 0x26: 2, 0x27: 2,
            # ... add more as needed
        }
        return opcode_params.get(opcode, 0)

    def _determine_event_class(self, event_script) -> str:
        """Determine event class (A, B, C, D) from script context."""
        # This is a simplified implementation
        # In practice, you'd need to analyze the script's usage context
        return "B"  # Default to B class

    def _determine_script_index(self, event_script) -> int:
        """Determine script index within its class."""
        # This would need to be determined from the event list structure
        return 0  # Simplified

    def get_zone_script(self, zone: "Zone", event_class: str, script_index: int) -> CompiledScript | None:
        """Get a specific script for a zone."""
        signature = f"{zone.index:02X}-{event_class}-{script_index:02X}"
        return self.compiled_scripts.get(signature)

    def export_zone_scripts(self, zone: "Zone") -> str:
        """Export all scripts for a zone to text format."""
        scripts = self.load_zone_events(zone)
        lines = [f"# Zone {zone.index}: {zone.clean_name}"]

        for script in scripts:
            lines.append("")
            lines.append(str(script.original_script))

        return "\n".join(lines)


# =============================================================================
# Enhanced Text Processor for Lufia II
# =============================================================================

class LufiaTextProcessor(TextProcessor):
    """Text processor specifically for Lufia II's compression format."""

    CHARACTER_MAP = {
        0x00: "<END EVENT>",
        0x01: "<END MESSAGE>",
        0x03: "\n",
        0x04: "<PAUSE>",
        0x09: "$MAXIM$",
        0x0A: "<COMPRESS>",
        0x0B: "<CURSOR>",
        0x0C: "?\n",
        0x0D: " \n",
        0x0E: ",\n",
        0x0F: ".\n",
    }

    REVERSE_CHARACTER_MAP = {v: k for k, v in CHARACTER_MAP.items()}

    def __init__(self) -> None:
        self.word_dictionary = self._load_word_dictionary()

    def _load_word_dictionary(self) -> dict[int, str]:
        """Load the word dictionary for text compression."""
        # This would load from the Word class mentioned in events.py
        return {}

    def encode(self, text: str) -> bytes:
        """Encode text with Lufia II compression."""
        result = bytearray()
        i = 0

        while i < len(text):
            # Look for special tags
            found_tag = False
            for tag, byte_val in self.REVERSE_CHARACTER_MAP.items():
                if text[i:].startswith(tag):
                    result.append(byte_val)
                    i += len(tag)
                    found_tag = True
                    break

            if not found_tag:
                # Check for compressible words
                word_match = self._find_compressible_word(text[i:])
                if word_match:
                    word, word_index = word_match
                    # Encode as compressed word (05/06 + index)
                    if word_index < 256:
                        result.extend([0x05, word_index])
                    else:
                        result.extend([0x06, word_index - 256])
                    i += len(word)
                else:
                    # Regular character
                    result.append(ord(text[i]))
                    i += 1

        return bytes(result)

    def decode(self, data: bytes) -> str:
        """Decode Lufia II compressed text."""
        result = ""
        i = 0

        while i < len(data):
            byte_val = data[i]

            if byte_val in [0x05, 0x06] and i + 1 < len(data):
                # Compressed word
                index = data[i + 1]
                if byte_val == 0x06:
                    index += 256

                word = self.word_dictionary.get(index, f"<WORD{index}>")
                result += word
                i += 2
            elif byte_val in self.CHARACTER_MAP:
                result += self.CHARACTER_MAP[byte_val]
                i += 1
            else:
                if 32 <= byte_val <= 126:
                    result += chr(byte_val)
                else:
                    result += f"<{byte_val:02X}>"
                i += 1

        return result

    def _find_compressible_word(self, text: str) -> tuple[str, int] | None:
        """Find if text starts with a compressible word."""
        for word_index, word in self.word_dictionary.items():
            if text.startswith(word):
                return word, word_index
        return None


# =============================================================================
# Enhanced Instructions for Lufia II
# =============================================================================

class LufiaTextInstruction(TextInstruction):
    """Enhanced text instruction with Lufia II compression support."""

    def __init__(self, speaker_id: int | None = None, text: str = "") -> None:
        super().__init__(speaker_id, text)
        self.text_processor = LufiaTextProcessor()

    def parse_parameters(self, data: bytes) -> tuple[list[Any], bytes]:
        """Parse text with Lufia II compression."""
        # Find the end of text data
        text_end = 0
        for i, byte in enumerate(data):
            if byte in [0x00, 0x01]:  # Text terminators
                text_end = i + 1
                break

        if text_end == 0:
            text_end = len(data)

        text_data = data[:text_end]
        remaining = data[text_end:]

        # Decode text
        self.text = self.text_processor.decode(text_data)

        # Extract speaker if present
        if text_data and text_data[0] == 0x09:  # VOICE tag
            if len(text_data) > 1:
                self.speaker_id = text_data[1]

        self.parameters = [("text", text_data)]
        return self.parameters, remaining

    def compile_parameters(self) -> bytes:
        """Compile text with Lufia II compression."""
        return self.text_processor.encode(self.text)


# Register Lufia-specific instructions
InstructionFactory.register(0x13, LufiaTextInstruction)
for speaker_code in range(0x61, 0x68):  # Party member speak instructions
    InstructionFactory.register(speaker_code, LufiaTextInstruction)


# =============================================================================
# Factory function for integration
# =============================================================================

def create_lufia_event_system(config: EventSystemConfig | None = None) -> LufiaEventSystem:
    """Factory function to create a properly configured Lufia II event system."""
    if config is None:
        config = EventSystemConfig()
        config.text_processor = LufiaTextProcessor
        config.instruction_set = "lufia2_na"

    return LufiaEventSystem(config)


# =============================================================================
# Zone Integration Helper
# =============================================================================

class ZoneEventManager:
    """Helper class to manage events for zones."""

    def __init__(self) -> None:
        self.event_system = create_lufia_event_system()

    def load_zone_events(self, zone: "Zone") -> list[CompiledScript]:
        """Load all events for a zone."""
        return self.event_system.load_zone_events(zone)

    def get_npc_script(self, zone: "Zone") -> CompiledScript | None:
        """Get the NPC loader script for a zone."""
        return self.event_system.get_zone_script(zone, "X", 0)

    def get_tile_script(self, zone: "Zone", tile_index: int) -> CompiledScript | None:
        """Get a tile interaction script (D class)."""
        return self.event_system.get_zone_script(zone, "D", tile_index)

    def get_npc_dialogue(self, zone: "Zone", npc_index: int) -> CompiledScript | None:
        """Get NPC dialogue script (C class)."""
        # NPC index mapping: NPC index + 0x4F = Script index (for normal NPCs)
        script_index = npc_index + 0x4F if npc_index >= 0x50 else npc_index
        return self.event_system.get_zone_script(zone, "C", script_index)

    def export_zone_events(self, zone: "Zone") -> str:
        """Export all zone events to text format."""
        return self.event_system.export_zone_scripts(zone)
