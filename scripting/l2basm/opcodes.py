"""The L2BASM opcode table (monster, capsule, item, spell and IP-effect scripts and $42 subroutines).

Operand counts come from the old ``structures.battlescript.op_codes`` table (``_OLD_PARAMS``, removed since), with the corrections in
``CORRECTIONS``. Opcodes with known meaning get named, typed operands in ``_TYPED``; the rest get one ``U8`` per
operand byte, named ``op_XX``. Opcodes missing from both tables are unknown: the parser stops a path there.
"""

from scripting.core import U8, U16, Flow, Jump, Language, OpcodeSpec, OperandKind


_OLD_PARAMS: dict[int, int] = {
    0x00: 0,  # END
    0x01: 0,  # Execute (don't exit) > I.E. For multiple actions
    0x02: 0,  # Reset's game.
    0x03: 2,  # GoTo
    0x04: 2,  # On Failure GoTo
    0x05: 3,  # On Chance GoTo
    0x06: 5,  # If Equal GoTo
    0x07: 5,  # If Not Equal GoTo
    0x08: 5,  # If Greater GoTo
    0x09: 5,  # If Less GoTo
    0x0a: 5,  # If Greater or Equal GoTo
    0x0b: 5,  # If Less or Equal GoTo
    0x0c: 3,  # Register Set
    0x0d: 3,  # Register ADD +
    0x0e: 3,  # Register SUB -
    0x0f: 3,  # Register MUL *
    0x10: 3,  # Register DIV /
    0x11: 2,  # Register Rand
    0x12: 2,  # Unknown
    0x13: 2,  # Register Set Stat
    0x14: 2,  # Stat Set Register
    0x15: 2,  # Register Set Stat Self
    0x16: 3,  # Register AND
    0x17: 3,  # Register OR
    0x18: 3,  # Register XOR
    0x19: 1,  # Unknown
    0x1a: 1,  # Register NEG
    0x1b: 1,  # Unknown
    0x1c: 1,  # Unknown
    0x1d: 1,  # Cancel and continue?
    0x1e: 1,  # Display Attack Name
    0x1f: 2,  # Add Element
    0x20: 2,  # Critical Hit Chance
    0x21: 5,  # Physical Damage
    0x22: 5,  # Magical Damage
    0x23: 2,  # Bunny Sword
    0x24: 4,  # Restore Stat
    0x25: 2,  # Intensify Stat
    0x26: 2,  # Recover From Status
    0x27: 2,  # Apply Status Effect
    0x28: 0,  # Physical Attack
    0x29: 0,  # Defend
    0x2a: 0,  # Flee
    0x2b: 2,  # Use Item
    0x2c: 1,  # Monster Cast Spell
    0x2d: 1,  # Call Companions
    0x2e: 0,  # Unknown
    0x2f: 1,  # Unknown
    0x30: 1,  # Unknown
    0x31: 0,  # Unknown
    0x32: 1,  # Target
    0x33: 0,  # Reset game
    0x34: 0,  # Reset game
    0x35: 1,  # Special Item
    0x36: 1,  # Unknown
    0x37: 0,  # Weapon Physical Attack
    0x38: 0,  # Reset game
    0x39: 0,  # Reset game
    0x3a: 0,  # Reset game
    0x3b: 0,  # Reset game
    0x3c: 0,  # Add INT to Damage
    0x3e: 1,  # Display CM Attack Name
    0x3f: 3,  # Learnable Attack
    0x40: 1,  # Unknown
    0x41: 0,  # Wait > Checking Situation
    0x42: 2,  # Subroutine
    0x43: 0,  # Return from Subroutine
    0x44: 2,  # Unknown
    0x47: 2,  # Unknown
    0x49: 0,  # Unknown
    0x4d: 0,  # Unknown
    0x4e: 2,  # Load Register > Stat Register
    0x4f: 0,  # Exit without executing effect code
    0x50: 0,  # No Re-targetting Spells
    0x51: 0,  # Dark Reflector Effect
    0x52: 0,  # Reflector?
    0x53: 1,  # Unknown
    0x54: 1,  # Cast IP Spell?
    0x55: 3,  # Unsigned Division?
    0x56: 2,  # Attack Name Duration
    0x57: 3,  # Item Effectiveness > Spell
    0x58: 0,  # Empty temp stat registers. (Eerie Light Effect)
    0x59: 0,  # Empty temp stat registers. (Enemies)
    0x5a: 1,  # Call Battle Animation
    0x5b: 0,  # Lose on Master Suicide
    0x5c: 0,  # Hide damage dealt
}

_COMMENTS: dict[int, str] = {
    0x00: 'END',
    0x01: "Execute (don't exit) > I.E. For multiple actions",
    0x02: "Reset's game.",
    0x03: 'GoTo',
    0x04: 'On Failure GoTo',
    0x05: 'On Chance GoTo',
    0x06: 'If Equal GoTo',
    0x07: 'If Not Equal GoTo',
    0x08: 'If Greater GoTo',
    0x09: 'If Less GoTo',
    0x0a: 'If Greater or Equal GoTo',
    0x0b: 'If Less or Equal GoTo',
    0x0c: 'Register Set',
    0x0d: 'Register ADD +',
    0x0e: 'Register SUB -',
    0x0f: 'Register MUL *',
    0x10: 'Register DIV /',
    0x11: 'Register Rand',
    0x12: 'Unknown',
    0x13: 'Register Set Stat',
    0x14: 'Stat Set Register',
    0x15: 'Register Set Stat Self',
    0x16: 'Register AND',
    0x17: 'Register OR',
    0x18: 'Register XOR',
    0x19: 'Unknown',
    0x1a: 'Register NEG',
    0x1b: 'Unknown',
    0x1c: 'Unknown',
    0x1d: 'Cancel and continue?',
    0x1e: 'Display Attack Name',
    0x1f: 'Add Element',
    0x20: 'Critical Hit Chance',
    0x21: 'Physical Damage',
    0x22: 'Magical Damage',
    0x23: 'Bunny Sword',
    0x24: 'Restore Stat',
    0x25: 'Intensify Stat',
    0x26: 'Recover From Status',
    0x27: 'Apply Status Effect',
    0x28: 'Physical Attack',
    0x29: 'Defend',
    0x2a: 'Flee',
    0x2b: 'Use Item',
    0x2c: 'Monster Cast Spell',
    0x2d: 'Call Companions',
    0x2e: 'Unknown',
    0x2f: 'Unknown',
    0x30: 'Unknown',
    0x31: 'Unknown',
    0x32: 'Target',
    0x33: 'Reset game',
    0x34: 'Reset game',
    0x35: 'Special Item',
    0x36: 'Unknown',
    0x37: 'Weapon Physical Attack',
    0x38: 'Reset game',
    0x39: 'Reset game',
    0x3a: 'Reset game',
    0x3b: 'Reset game',
    0x3c: 'Add INT to Damage',
    0x3e: 'Display CM Attack Name',
    0x3f: 'Learnable Attack',
    0x40: 'Unknown',
    0x41: 'Wait > Checking Situation',
    0x42: 'Subroutine',
    0x43: 'Return from Subroutine',
    0x44: 'Unknown',
    0x47: 'Unknown',
    0x49: 'Unknown',
    0x4d: 'Unknown',
    0x4e: 'Load Register > Stat Register',
    0x4f: 'Exit without executing effect code',
    0x50: 'No Re-targetting Spells',
    0x51: 'Dark Reflector Effect',
    0x52: 'Reflector?',
    0x53: 'Unknown',
    0x54: 'Cast IP Spell?',
    0x55: 'Unsigned Division?',
    0x56: 'Attack Name Duration',
    0x57: 'Item Effectiveness > Spell',
    0x58: 'Empty temp stat registers. (Eerie Light Effect)',
    0x59: 'Empty temp stat registers. (Enemies)',
    0x5a: 'Call Battle Animation',
    0x5b: 'Lose on Master Suicide',
    0x5c: 'Hide damage dealt',
}

SUBROUTINES: dict[int, str] = {
    # What each ``42 XX 00`` subroutine does (info/L2_Subroutines$42XX.txt); unlisted ones are undocumented.
    0x00: 'Weak Vs Fire',
    0x01: 'Weak Vs Thunder',
    0x02: 'Weak Vs Water',
    0x03: 'Weak Vs Ice',
    0x04: 'Eff. against Flying attacks + impervious to Earth',
    0x05: 'Weakness against Light',
    0x06: 'Protection against Fire',
    0x07: 'Protection against Thunder',
    0x08: 'Protection against Water',
    0x09: 'Protection against Ice',
    0x0a: 'Protection against Light',
    0x0b: 'Protection against neutral elemental attacks?',
    0x0c: 'Weakness against Eff. against Dragons attacks',
    0x0d: 'Weakness against Shadow',
    0x0e: 'Protection against Shadow',
    0x0f: 'makes you a Hard enemy? (to check...)',
    0x10: 'makes you an insect? (to check...)',
    0x11: "Full protection against Poisoning, Silence, Paralysis, Confusion and Sleep.Not protection against Instant Death, Effect 6 and Mirror.(For a lot of monsters (bosses...), 'Seethru cape', 'Seethru silk'",
    0x12: "Full protection against Instant Death but HP recovery spells inflict damage! (i.e.: you're undead)(Not used for items. Common for monsters)",
    0x13: '??? (For Core monsters only. Not used for items), (greatly reduce all magic DMG?)',
    0x14: '(For Gorem monsters only. Not used for items),Protection against all attacks except neutral elemental attacks?',
    0x15: '???',
    0x16: '(Not used for items/monster/caps.monsters)',
    0x17: 'Protection against hard attacks?(Not used for items. Used for Demise and Leech',
    0x18: 'Good protection against a certain elemental damage.(Gold gloves, Gold shield, Holy shield, Plati gloves, Plati shield, Rune gloves (IP effect))(not used for monsters)',
    0x19: 'Full protection against a certain elemental damage. Ex.: (Apron shield, Bolt shield, Cryst shield, 0C 81 02 00 42 19 00 Fire attacks miss Dark mirror, Flame shield, Water gaunt (IP effect)) (not used for monsters)',
    0x1a: 'elemental mirror 0C 81 02 00 42 1A 00 Fire attacks bounce back at attacker (like with Mirror) (Agony helm, Aqua helm, Boom turban, Brill helm, Hairpin, Ice hairband (IP effect)) (not used for monsters)',
    0x1b: '??? (not used for items / monsters)',
    0x22: '??? (Nosferatu)',
    0x23: '???',
    0x24: "'Miracle care' IP effect (Pearl shield):FULL PROTECTION AGAINST ALL DAMAGE!",
}

CRASH_CODES = frozenset({0x02, 0x31, 0x33, 0x34, 0x38, 0x39, 0x3A, 0x3B})
"""Opcodes that reset or hang the game when a script reaches them (``02``, ``33``, ``34``, ``38``-``3B`` reset)."""

CORRECTIONS: dict[int, int] = {
    0x11: 1,  # RAND reg: one register byte (info/L2_Subroutines$42XX.txt, "11 81 / RAND reg($81)")
    0x2C: 1,  # cast spell: spell index (missing from older op_codes tables)
    0x46: 1,  # not in L2_Effects.txt; item armor scripts 252-322 read `46 xx` then a clean stream to END
}

PARAM_COUNTS: dict[int, int] = {**_OLD_PARAMS, **CORRECTIONS}

_REG_VALUE_JUMP: tuple[OperandKind, ...] = (U8("reg"), U16("value"), Jump())

_TYPED: dict[int, tuple[str, tuple[OperandKind, ...], Flow]] = {
    0x00: ("end", (), Flow.END),
    0x01: ("execute", (), Flow.CONTINUE),
    0x03: ("goto", (Jump(),), Flow.GOTO),
    0x04: ("on_fail", (Jump(),), Flow.BRANCH),
    0x05: ("on_chance", (U8("chance"), Jump()), Flow.BRANCH),
    0x06: ("if_eq", _REG_VALUE_JUMP, Flow.BRANCH),
    0x07: ("if_ne", _REG_VALUE_JUMP, Flow.BRANCH),
    0x08: ("if_gt", _REG_VALUE_JUMP, Flow.BRANCH),
    0x09: ("if_lt", _REG_VALUE_JUMP, Flow.BRANCH),
    0x0A: ("if_ge", _REG_VALUE_JUMP, Flow.BRANCH),
    0x0B: ("if_le", _REG_VALUE_JUMP, Flow.BRANCH),
    0x0C: ("set_reg", (U8("reg"), U16("value")), Flow.CONTINUE),
    0x0D: ("add_reg", (U8("reg"), U16("value")), Flow.CONTINUE),
    0x0E: ("sub_reg", (U8("reg"), U16("value")), Flow.CONTINUE),
    0x0F: ("mul_reg", (U8("reg"), U16("value")), Flow.CONTINUE),
    0x10: ("div_reg", (U8("reg"), U16("value")), Flow.CONTINUE),
    0x11: ("rand", (U8("reg"),), Flow.CONTINUE),
    0x1E: ("display_name_monster", (U8("name"),), Flow.CONTINUE),
    0x21: ("physical_damage", (U16("element"), U16("base"), U8("extra")), Flow.CONTINUE),
    0x22: ("magical_damage", (U16("element"), U16("base"), U8("extra")), Flow.CONTINUE),
    0x27: ("apply_status", (U8("kind"), U8("prob")), Flow.CONTINUE),
    0x28: ("physical_attack", (), Flow.CONTINUE),
    0x29: ("defend", (), Flow.CONTINUE),
    0x2A: ("flee", (), Flow.CONTINUE),
    0x2B: ("use_item", (U16("item"),), Flow.CONTINUE),
    0x2C: ("cast_spell", (U8("spell"),), Flow.CONTINUE),
    0x32: ("target", (U8("target"),), Flow.CONTINUE),
    0x3E: ("display_name", (U8("name"),), Flow.CONTINUE),
    0x3F: ("learnable", (U8("slot"), Jump()), Flow.BRANCH),
    0x42: ("call", (U8("subroutine"), U8("zero")), Flow.CONTINUE),
    0x43: ("return", (), Flow.END),
    0x5A: ("battle_anim", (U8("anim"),), Flow.CONTINUE),
}


def _spec(opcode: int) -> OpcodeSpec:
    if opcode in _TYPED:
        name, operands, flow = _TYPED[opcode]
        return OpcodeSpec(opcode, name, operands, flow, _COMMENTS.get(opcode, ""))
    return OpcodeSpec(
        opcode, f"op_{opcode:02X}", tuple(U8("arg") for _ in range(PARAM_COUNTS[opcode])), comment=_COMMENTS.get(opcode, "")
    )


L2BASM = Language("L2BASM", {opcode: _spec(opcode) for opcode in sorted(PARAM_COUNTS)})
