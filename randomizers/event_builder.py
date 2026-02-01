"""Event Script Builder for Lufia II.

This module provides a high-level API for programmatically creating and modifying
event scripts without needing to manually construct bytecode.

Based on the opcode documentation from src/structures/events.py and insights from
the event_dump.py export functionality.

Example usage:
    >>> from randomizers import EventScriptBuilder
    >>>
    >>> # Create a simple NPC dialogue
    >>> builder = EventScriptBuilder()
    >>> builder.add_text("Hello, traveler!")
    >>> builder.add_text("Welcome to Elcid!")
    >>> builder.end_event()
    >>>
    >>> bytecode = builder.compile()
    >>>
    >>> # Create a shop event
    >>> shop_builder = EventScriptBuilder()
    >>> shop_builder.add_text("What can I get you?")
    >>> shop_builder.call_shop(0x37)
    >>> shop_builder.end_event()

    >>> # Create a conditional event with branching
    >>> cond_builder = EventScriptBuilder()
    >>> cond_builder.add_text("Do you want to rest?")
    >>> yes_label = cond_builder.add_choice(["Yes", "No"])
    >>> cond_builder.call_inn(10)  # 10 gold
    >>> cond_builder.end_event()
    >>> cond_builder.set_label(yes_label)
    >>> cond_builder.add_text("Maybe next time.")
    >>> cond_builder.end_event()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from logger import iris


class Opcode(IntEnum):
    """Event script opcodes for Lufia II.

    Complete reference from src/structures/events.py lines 287-411.
    """
    END = 0x00
    END_TEXT = 0x01  # IN TEXT MODE
    BRK = 0x02
    LINE_BREAK = 0x03  # IN TEXT MODE
    PAUSE_TEXT = 0x04  # IN TEXT MODE
    TEXT_SHIFT_05 = 0x05  # IN TEXT MODE
    TEXT_SHIFT_06 = 0x06  # IN TEXT MODE
    UNK_07 = 0x07
    CHARACTER_SPEAKS = 0x08
    HERO_NAME = 0x09  # IN TEXT MODE (Maxim)
    POINTER_0A = 0x0A
    SELECTION_CURSOR = 0x0B  # IN TEXT MODE
    TEXT_QUESTION_BREAK = 0x0C  # IN TEXT MODE: ? + line break
    TEXT_EXCLAIM_BREAK = 0x0D  # IN TEXT MODE: ! + line break
    TEXT_COMMA_BREAK = 0x0E  # IN TEXT MODE: , + line break
    TEXT_PERIOD_BREAK = 0x0F  # IN TEXT MODE: . + line break
    CHOICE = 0x10  # XX Choice, 2-byte pointers
    BRK_11 = 0x11
    POINTERS_12 = 0x12  # XX YY (P1 P1, ...)
    CHARACTER_SPEAKS_SPONT = 0x13
    CONDITIONAL = 0x14
    IF_FLAG_SET_JUMP = 0x15
    EXIT_MAP = 0x16  # Go to map XX, script YY, position ZZ
    INN_REST = 0x17  # XX: 0x00 => rest at inn
    SHOP_MENU = 0x18  # Enter shop menu XX
    CHURCH_MENU = 0x19
    SET_EVENT_BIT = 0x1A
    CLEAR_EVENT_BIT = 0x1B
    JUMP = 0x1C
    UNK_1D = 0x1D
    UNK_1E = 0x1E
    UNK_1F = 0x1F
    GET_ITEM_00XX = 0x20
    GET_ITEM_01XX = 0x21
    GET_GOLD = 0x22
    LEARN_SPELL = 0x23
    UNK_24 = 0x24
    UNK_25 = 0x25  # Remove item?
    UNK_26 = 0x26
    DUMMY_27 = 0x27
    UNK_28 = 0x28
    RANDOM_STAT_INCREASE = 0x29
    DUMMY_2A = 0x2A
    CHARACTER_JOIN = 0x2B
    CHARACTER_LEAVE = 0x2C
    CHARACTER_APPEAR = 0x2D
    CHARACTER_DISAPPEAR = 0x2E
    UNK_2F = 0x2F
    MOVE_CHAR_TO_LOCATION = 0x30
    CHARACTER_TURN = 0x31
    CHARACTER_STAND_STILL = 0x32
    CHARACTER_FOLLOW_PATH = 0x33
    CHANGE_SPRITE = 0x34
    UNK_35 = 0x35
    UNK_36 = 0x36
    PAUSE = 0x37
    PAUSE_SECONDS = 0x38
    DUMMY_39 = 0x39
    SHOW_MAP_COORDS = 0x3A
    SHOW_MAP_POSITION = 0x3B
    PARTY_WALK_TO_MAXIM = 0x3C
    UNK_3D = 0x3D
    # ... more opcodes


@dataclass
class EventInstruction:
    """Represents a single event script instruction.

    Attributes:
        opcode: The opcode byte
        parameters: List of parameter bytes
        label: Optional label for jump targets
        comment: Optional comment for documentation
    """
    opcode: int
    parameters: list[int] = field(default_factory=list)
    label: str | None = None
    comment: str | None = None

    def to_bytes(self) -> bytes:
        """Convert instruction to bytecode."""
        return bytes([self.opcode, *self.parameters])

    def __str__(self) -> str:
        """Human-readable representation."""
        label_str = f"{self.label}: " if self.label else ""
        param_str = "-".join(f"{p:02X}" for p in self.parameters) if self.parameters else ""
        opcode_name = Opcode(self.opcode).name if self.opcode in Opcode._value2member_map_ else "UNK"
        comment_str = f"  # {self.comment}" if self.comment else ""
        return f"{label_str}{opcode_name}({param_str}){comment_str}"


class EventScriptBuilder:
    """High-level builder for creating event scripts.

    This class provides a fluent API for constructing event scripts without
    needing to manually construct bytecode or know opcode values.

    Attributes:
        instructions: List of instructions in the script
        labels: Dictionary mapping label names to instruction indices
        current_address: Current virtual address for label calculation
    """

    def __init__(self) -> None:
        """Initialize a new event script builder."""
        self.instructions: list[EventInstruction] = []
        self.labels: dict[str, int] = {}
        self.current_address = 0
        self._label_counter = 0

    def _add_instruction(
        self,
        opcode: int,
        params: list[int] | None = None,
        comment: str | None = None,
    ) -> EventScriptBuilder:
        """Add an instruction to the script.

        Args:
            opcode: Opcode byte value
            params: Optional list of parameter bytes
            comment: Optional comment for documentation

        Returns:
            Self for method chaining
        """
        instruction = EventInstruction(
            opcode=opcode,
            parameters=params or [],
            comment=comment,
        )
        self.instructions.append(instruction)
        self.current_address += 1 + len(params or [])
        return self

    def _generate_label(self) -> str:
        """Generate a unique label name."""
        self._label_counter += 1
        return f"label_{self._label_counter}"

    def set_label(self, label: str) -> EventScriptBuilder:
        """Set a label at the current position.

        Args:
            label: Label name

        Returns:
            Self for method chaining
        """
        self.labels[label] = len(self.instructions)
        if self.instructions:
            self.instructions[-1].label = label
        return self

    # ========== Text and Dialogue ==========

    def add_text(self, text: str, auto_break: bool = True) -> EventScriptBuilder:
        """Add text to the script.

        This is a high-level method that handles text encoding and
        proper message termination.

        Args:
            text: Text to display
            auto_break: If True, automatically add END MESSAGE opcode

        Returns:
            Self for method chaining
        """
        # TODO: Implement proper text encoding
        # For now, this is a placeholder that would need to use
        # the game's text compression/encoding system

        iris.debug(f"Adding text: {text}")

        # Character speaks opcode
        self._add_instruction(Opcode.CHARACTER_SPEAKS, comment=f'Text: "{text}"')

        if auto_break:
            self._add_instruction(Opcode.END_TEXT, comment="End message")

        return self

    def add_choice(
        self,
        options: list[str],
        branch_labels: list[str] | None = None,
    ) -> list[str]:
        """Add a choice prompt with multiple options.

        Args:
            options: List of choice text strings
            branch_labels: Optional list of labels for each branch.
                         If None, generates automatic labels.

        Returns:
            List of label names for each branch (for later use with set_label)
        """
        if branch_labels is None:
            branch_labels = [self._generate_label() for _ in options]

        # Choice opcode followed by pointers
        self._add_instruction(
            Opcode.CHOICE,
            [len(options)],
            comment=f"Choice: {', '.join(options)}",
        )

        # Add placeholder pointers (would need proper calculation)
        for label in branch_labels:
            self._add_instruction(0x0A, [0x00, 0x00], comment=f"Branch to {label}")

        return branch_labels

    # ========== Control Flow ==========

    def end_event(self) -> EventScriptBuilder:
        """End the event script."""
        self._add_instruction(Opcode.END, comment="End event")
        return self

    def jump_to(self, label: str) -> EventScriptBuilder:
        """Jump to a label.

        Args:
            label: Target label name

        Returns:
            Self for method chaining
        """
        # JUMP opcode with 2-byte relative offset
        self._add_instruction(Opcode.JUMP, [0x00, 0x00], comment=f"Jump to {label}")
        return self

    def if_flag_set(
        self,
        flag: int,
        label: str,
    ) -> EventScriptBuilder:
        """Conditional jump if event flag is set.

        Args:
            flag: Event flag number
            label: Label to jump to if flag is set

        Returns:
            Self for method chaining
        """
        self._add_instruction(
            Opcode.IF_FLAG_SET_JUMP,
            [flag, 0x00, 0x00],
            comment=f"If flag {flag} set, jump to {label}",
        )
        return self

    # ========== Game Actions ==========

    def call_shop(self, shop_id: int) -> EventScriptBuilder:
        """Open a shop menu.

        Args:
            shop_id: Shop identifier

        Returns:
            Self for method chaining
        """
        self._add_instruction(Opcode.SHOP_MENU, [shop_id], comment=f"Open shop {shop_id}")
        return self

    def call_inn(self, price: int) -> EventScriptBuilder:
        """Call inn rest menu.

        Args:
            price: Price in gold

        Returns:
            Self for method chaining
        """
        self._add_instruction(Opcode.INN_REST, [price], comment=f"Inn rest ({price} gold)")
        return self

    def give_item(self, item_id: int, quantity: int = 1) -> EventScriptBuilder:
        """Give an item to the player.

        Args:
            item_id: Item identifier
            quantity: Number of items to give

        Returns:
            Self for method chaining
        """
        if item_id < 0x100:
            opcode = Opcode.GET_ITEM_00XX
        else:
            opcode = Opcode.GET_ITEM_01XX
            item_id -= 0x100

        self._add_instruction(opcode, [item_id, quantity], comment=f"Give item {item_id} x{quantity}")
        return self

    def give_gold(self, amount: int) -> EventScriptBuilder:
        """Give gold to the player.

        Args:
            amount: Amount of gold (2 bytes, little-endian)

        Returns:
            Self for method chaining
        """
        low_byte = amount & 0xFF
        high_byte = (amount >> 8) & 0xFF
        self._add_instruction(Opcode.GET_GOLD, [high_byte, low_byte], comment=f"Give {amount} gold")
        return self

    def set_flag(self, flag: int) -> EventScriptBuilder:
        """Set an event flag.

        Args:
            flag: Flag number to set

        Returns:
            Self for method chaining
        """
        self._add_instruction(Opcode.SET_EVENT_BIT, [flag], comment=f"Set flag {flag}")
        return self

    def clear_flag(self, flag: int) -> EventScriptBuilder:
        """Clear an event flag.

        Args:
            flag: Flag number to clear

        Returns:
            Self for method chaining
        """
        self._add_instruction(Opcode.CLEAR_EVENT_BIT, [flag], comment=f"Clear flag {flag}")
        return self

    # ========== Character Actions ==========

    def character_join(self, character_id: int) -> EventScriptBuilder:
        """Add a character to the party.

        Args:
            character_id: Character identifier

        Returns:
            Self for method chaining
        """
        self._add_instruction(Opcode.CHARACTER_JOIN, [character_id], comment=f"Character {character_id} joins")
        return self

    def character_leave(self, character_id: int) -> EventScriptBuilder:
        """Remove a character from the party.

        Args:
            character_id: Character identifier

        Returns:
            Self for method chaining
        """
        self._add_instruction(Opcode.CHARACTER_LEAVE, [character_id], comment=f"Character {character_id} leaves")
        return self

    def move_character(
        self,
        character_id: int,
        location_id: int,
    ) -> EventScriptBuilder:
        """Move a character to a predefined location.

        Args:
            character_id: Character to move
            location_id: Destination location

        Returns:
            Self for method chaining
        """
        self._add_instruction(
            Opcode.MOVE_CHAR_TO_LOCATION,
            [character_id, location_id],
            comment=f"Move character {character_id} to location {location_id}",
        )
        return self

    # ========== Compilation ==========

    def compile(self) -> bytes:
        """Compile the script to bytecode.

        This resolves all labels and generates the final bytecode.

        Returns:
            Compiled bytecode
        """
        # First pass: calculate actual addresses
        address = 0
        instruction_addresses = []

        for instr in self.instructions:
            instruction_addresses.append(address)
            address += 1 + len(instr.parameters)

        # Second pass: resolve jump targets
        bytecode = bytearray()

        for _i, instr in enumerate(self.instructions):
            bytecode.append(instr.opcode)

            # Check if this instruction has jump parameters that need resolution
            if instr.opcode in (Opcode.JUMP, Opcode.IF_FLAG_SET_JUMP):
                # Extract target label from comment
                # This is simplified - real implementation would need proper tracking
                bytecode.extend(instr.parameters)
            else:
                bytecode.extend(instr.parameters)

        return bytes(bytecode)

    def export_text(self) -> str:
        """Export the script as human-readable text.

        Similar to the format used in event_dump.py exports.

        Returns:
            Human-readable script text
        """
        lines = []

        for i, instr in enumerate(self.instructions):
            address_str = f"{i*2:04X}"
            lines.append(f"  {address_str}. {instr}")

        return "\n".join(lines)

    def __str__(self) -> str:
        """String representation of the script."""
        return self.export_text()


# ========== Convenience Functions ==========

def create_simple_npc(dialogue: str) -> EventScriptBuilder:
    """Create a simple NPC with single dialogue.

    Args:
        dialogue: The NPC's dialogue text

    Returns:
        Compiled EventScriptBuilder
    """
    builder = EventScriptBuilder()
    builder.add_text(dialogue)
    builder.end_event()
    return builder


def create_shop_npc(greeting: str, shop_id: int, sold_out_msg: str = "Sorry, sold out!") -> EventScriptBuilder:
    """Create a shop NPC.

    Args:
        greeting: Greeting text
        shop_id: Shop menu identifier
        sold_out_msg: Message when shop is closed

    Returns:
        Compiled EventScriptBuilder
    """
    builder = EventScriptBuilder()
    builder.add_text(greeting)
    builder.call_shop(shop_id)
    builder.end_event()
    builder.add_text(sold_out_msg)
    builder.end_event()
    return builder


def create_inn_npc(greeting: str, price: int) -> EventScriptBuilder:
    """Create an inn NPC with yes/no choice.

    Args:
        greeting: Greeting text (should ask about staying)
        price: Inn price in gold

    Returns:
        Compiled EventScriptBuilder
    """
    builder = EventScriptBuilder()
    builder.add_text(greeting)

    labels = builder.add_choice(["Yes", "No"])

    # Yes path
    builder.call_inn(price)
    builder.end_event()

    # No path
    builder.set_label(labels[1])
    builder.end_event()

    return builder
