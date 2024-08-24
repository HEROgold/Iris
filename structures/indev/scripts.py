from enum import IntEnum
import re
from string import ascii_letters, digits, punctuation
from typing import TypedDict


TEXT_PARAMETERS = {
    0x04: 1,
    0x05: 1,
    0x06: 1,
    0x0a: 2,
}
TEXT_TERMINATORS = {0x00, 0x01, 0x0b}
ASCII_VISIBLE = ascii_letters + digits + punctuation + ' '
CHARACTER_MAP = {
    0x00: '<END EVENT>',
    0x01: '<END MESSAGE>',
    0x03: '\n',
    0x04: '<PAUSE>',
    0x09: '$MAXIM$',
    0x0a: '<REPEAT>',
    0x0b: '<CHOICE>',
    0x0c: '?\n',
    0x0d: '!\n',
    0x0e: ',\n',
    0x0f: '.\n',
}
REVERSE_CHARACTER_MAP = {v: k for k, v in CHARACTER_MAP.items()}
TAG_MATCHER = re.compile(r'<([^>]*) ([^> ]*)>')
LINE_MATCHER = re.compile(r'^\s*([0-9a-fA-F]{1,4})\.', flags=re.MULTILINE)
ADDRESS_MATCHER = re.compile(r'@([0-9A-Fa-f]+)[^0-9A-Fa-f]', flags=re.DOTALL)

END_NPC_POINTER = 0x3ae4d
END_EVENT_POINTER = 0x7289e
FREE_SPACE = []


class EventInstructions(TypedDict):
    opcode: int
    params: list[int] | None
    comment: str | None

class ParamDict(TypedDict):
    text: str
    pointers: list[int] # [int] ?
    address: int
    variable: int

class ParamEnum(IntEnum):
    TEXT = 0XFF0
    POINTERS = 0XFF1
    ADDRESS = 0XFF2
    VARIABLE = 0XFF3


class ScriptParser:
    def parse_params(self, params: list[int], options: dict[int, ParamDict]):
        values = []
        for param in params:
            if param == ParamEnum.TEXT:
                values.append(options[ParamEnum.TEXT.value])
            elif param == ParamEnum.POINTERS:
                values.append(options[ParamEnum.POINTERS.value])
            elif param == ParamEnum.ADDRESS:
                values.append(options[ParamEnum.ADDRESS.value])
            elif param == ParamEnum.VARIABLE:
                values.append(options[ParamEnum.VARIABLE.value])
            else:
                pass
        return values

event_instructions: dict[int, EventInstructions] = {
    0: {'opcode': 0x00, 'params': [0], 'comment': 'End Event'},
    1: {'opcode': 0x01, 'params': [2], 'comment': 'Check for item (as in locked doors)'},
    2: {'opcode': 0x02, 'params': [2], 'comment': 'Check for item (as in locked doors)'},
    3: {'opcode': 0x03, 'params': [2], 'comment': 'Check for item (as in locked doors)'},
    4: {'opcode': 0x04, 'params': [2], 'comment': 'Check for item (as in locked doors)'},
    5: {'opcode': 0x05, 'params': [2], 'comment': 'Check for item (as in locked doors)'},
    6: {'opcode': 0x06, 'params': [2], 'comment': 'Check for item (as in locked doors)'},
    7: {'opcode': 0x07, 'params': [1], 'comment': 'UNVERIFIED'},
    8: {'opcode': 0x08, 'params': [4080], 'comment': None},
    9: {'opcode': 0x0c, 'params': [0], 'comment': 'NOP?'},
    10: {'opcode': 0x0d, 'params': [0], 'comment': 'NOP?'},
    11: {'opcode': 0x10, 'params': [4081], 'comment': 'Set Up Branching Event'},
    12: {'opcode': 0x11, 'params': [0], 'comment': 'ERROR?'},
    13: {'opcode': 0x12, 'params': [1, 4081], 'comment': 'Branch on Variable'},
    14: {'opcode': 0x13, 'params': [4080], 'comment': ''},
    15: {'opcode': 0x14, 'params': [4083], 'comment': 'Branch on Game State (inventory, stats, etc.)'},
    16: {'opcode': 0x15, 'params': [1, 4082], 'comment': 'Branch on Flag'},
    17: {'opcode': 0x16, 'params': [1, 1, 1], 'comment': 'Warp to Map & Event'},
    18: {'opcode': 0x17, 'params': [1], 'comment': 'Call Inn at Price'},
    19: {'opcode': 0x18, 'params': [1], 'comment': 'Call Shop'},
    20: {'opcode': 0x19, 'params': [0], 'comment': 'Call Church'},
    21: {'opcode': 0x1a, 'params': [1], 'comment': 'Set Event Flag'},
    22: {'opcode': 0x1b, 'params': [1], 'comment': 'Clear Event Flag'},
    23: {'opcode': 0x1c, 'params': [4082], 'comment': 'Jump'},
    24: {'opcode': 0x1d, 'params': [1, 1], 'comment': 'Set Variable'},
    25: {'opcode': 0x1e, 'params': [1, 1], 'comment': 'Add Value to Variable'},
    26: {'opcode': 0x20, 'params': [1, 1], 'comment': 'Get Item 0XX'},
    27: {'opcode': 0x21, 'params': [1, 1], 'comment': 'Get Item 1XX'},
    28: {'opcode': 0x22, 'params': [2], 'comment': 'Get Gold'},
    29: {'opcode': 0x23, 'params': [1, 1], 'comment': 'Learn Spell'},
    30: {'opcode': 0x24, 'params': [1, 1], 'comment': 'Remove Item 0XX'},
    31: {'opcode': 0x25, 'params': [1, 1], 'comment': 'Remove Item 1XX'},
    32: {'opcode': 0x28, 'params': [0], 'comment': None},
    33: {'opcode': 0x29, 'params': [1, 1, 1], 'comment': 'Increase party member stats'},
    34: {'opcode': 0x2b, 'params': [1], 'comment': 'Character Joins Party'},
    35: {'opcode': 0x2c, 'params': [1], 'comment': 'Character Leaves party'},
    36: {'opcode': 0x2d, 'params': [1], 'comment': 'Character Appears'},
    37: {'opcode': 0x2e, 'params': [1], 'comment': 'Character Disappears'},
    38: {'opcode': 0x30, 'params': [1, 1], 'comment': 'Teleport Character'},
    39: {'opcode': 0x31, 'params': [1, 1], 'comment': 'Change Facing'},
    40: {'opcode': 0x32, 'params': [1, 1], 'comment': 'Change NPC wander behavior (misc byte)'},
    41: {'opcode': 0x33, 'params': [1, 1], 'comment': 'Move Character to Location'},
    42: {'opcode': 0x34, 'params': [1, 1], 'comment': 'Change Character Sprite'},
    43: {'opcode': 0x35, 'params': [1, 1, 1], 'comment': 'Move roaming NPC'},
    44: {'opcode': 0x37, 'params': [1], 'comment': 'Pause'},
    45: {'opcode': 0x38, 'params': [1], 'comment': 'Pause (Longer)'},
    46: {'opcode': 0x39, 'params': [0], 'comment': None},
    47: {'opcode': 0x3b, 'params': [1], 'comment': 'Move Camera'},
    48: {'opcode': 0x3c, 'params': [0], 'comment': 'Gather Behind Maxim'},
    49: {'opcode': 0x3d, 'params': [1], 'comment': 'Hide Behind Maxim'},
    50: {'opcode': 0x40, 'params': [2], 'comment': 'Key check? (Only used in Ancient Cave lobby)'},
    51: {'opcode': 0x42, 'params': [0], 'comment': 'DUPLICATE - 00 End Event'},
    52: {'opcode': 0x41, 'params': [1, 1], 'comment': 'Camera related (follow for X steps?)'},
    53: {'opcode': 0x43, 'params': [1, 1], 'comment': 'Overwrite Map Tiles'},
    54: {'opcode': 0x45, 'params': [1, 1, 1], 'comment': None},
    55: {'opcode': 0x47, 'params': [1], 'comment': 'Thinking On/Off'},
    56: {'opcode': 0x48, 'params': [1, 1], 'comment': None},
    57: {'opcode': 0x49, 'params': [1], 'comment': None},
    58: {'opcode': 0x4a, 'params': [1], 'comment': None},
    59: {'opcode': 0x4b, 'params': [1], 'comment': 'Play BGM'},
    60: {'opcode': 0x4c, 'params': [1], 'comment': 'Play Sound'},
    61: {'opcode': 0x4d, 'params': [1], 'comment': None},
    62: {'opcode': 0x4f, 'params': [1], 'comment': None},
    63: {'opcode': 0x50, 'params': [0], 'comment': None},
    64: {'opcode': 0x51, 'params': [0], 'comment': None},
    65: {'opcode': 0x53, 'params': [1], 'comment': 'Invoke Battle'},
    66: {'opcode': 0x54, 'params': [1], 'comment': 'Open locked door?'},
    67: {'opcode': 0x55, 'params': [1], 'comment': None},
    68: {'opcode': 0x56, 'params': [0], 'comment': 'Stop Earthquake'},
    69: {'opcode': 0x57, 'params': [0], 'comment': None},
    70: {'opcode': 0x58, 'params': [1], 'comment': 'Fadeout'},
    71: {'opcode': 0x59, 'params': [1], 'comment': 'Luminosity'},
    72: {'opcode': 0x5a, 'params': [1, 1, 1], 'comment': 'Start Earthquake'},
    73: {'opcode': 0x5b, 'params': [1, 1], 'comment': 'Play Cutscene'},
    74: {'opcode': 0x5e, 'params': [1], 'comment': None},
    75: {'opcode': 0x60, 'params': [1, 1], 'comment': None},
    76: {'opcode': 0x61, 'params': [4080], 'comment': 'Maxim Speaks'},
    77: {'opcode': 0x62, 'params': [4080], 'comment': 'Selan Speaks'},
    78: {'opcode': 0x63, 'params': [4080], 'comment': 'Guy Speaks'},
    79: {'opcode': 0x64, 'params': [4080], 'comment': 'Artea Speaks'},
    80: {'opcode': 0x65, 'params': [4080], 'comment': 'Dekar Speaks'},
    81: {'opcode': 0x66, 'params': [4080], 'comment': 'Tia Speaks'},
    82: {'opcode': 0x67, 'params': [4080], 'comment': 'Lexis Speaks'},
    83: {'opcode': 0x68, 'params': [1, 1], 'comment': 'Load NPC'},
    84: {'opcode': 0x69, 'params': [1], 'comment': 'Set Map Properties (escapable, etc.)'},
    85: {'opcode': 0x6a, 'params': [1, 4082], 'comment': 'Branch on NOT Flag'},
    86: {'opcode': 0x6b, 'params': [0], 'comment': None},
    87: {'opcode': 0x6c, 'params': [1, 1, 1], 'comment': 'Move Character by Distance'},
    88: {'opcode': 0x6d, 'params': [4080], 'comment': 'Credits Text'},
    89: {'opcode': 0x6e, 'params': [4080], 'comment': 'Credits Text'},
    90: {'opcode': 0x6f, 'params': [1], 'comment': 'Change Music'},
    91: {'opcode': 0x70, 'params': [0], 'comment': 'Silence'},
    92: {'opcode': 0x71, 'params': [0], 'comment': None},
    93: {'opcode': 0x72, 'params': [0], 'comment': None},
    94: {'opcode': 0x73, 'params': [1, 1], 'comment': 'Play Animation'},
    95: {'opcode': 0x74, 'params': [1], 'comment': 'Set Battle BG'},
    96: {'opcode': 0x75, 'params': [0], 'comment': None},
    97: {'opcode': 0x76, 'params': [0], 'comment': None},
    98: {'opcode': 0x77, 'params': [1], 'comment': 'DUPLICATE - BE'},
    99: {'opcode': 0x78, 'params': [0], 'comment': None},
    100: {'opcode': 0x79, 'params': [0], 'comment': None},
    101: {'opcode': 0x7b, 'params': [1, 1], 'comment': 'Load Monster NPC'},
    102: {'opcode': 0x7c, 'params': [1], 'comment': 'Change Ship Type'},
    103: {'opcode': 0x7d, 'params': [1], 'comment': 'Relocate Ship'},
    104: {'opcode': 0x7e, 'params': [1], 'comment': 'Set Ship Exists/Un-exists'},
    105: {'opcode': 0x7f, 'params': [1], 'comment': 'Set Party On/Off Ship'},
    106: {'opcode': 0x80, 'params': [1], 'comment': 'Set Ship Sprite'},
    107: {'opcode': 0x81, 'params': [1], 'comment': 'Capsule Monster Joins & Renames'},
    108: {'opcode': 0x82, 'params': [0], 'comment': None},
    109: {'opcode': 0x83, 'params': [1], 'comment': 'Call Exit (Only used for Chaed)'},
    110: {'opcode': 0x85, 'params': [1, 1], 'comment': None},
    111: {'opcode': 0x86, 'params': [1, 1], 'comment': 'Character Movement?'},
    112: {'opcode': 0x87, 'params': [1, 1], 'comment': None},
    113: {'opcode': 0x88, 'params': [0], 'comment': None},
    114: {'opcode': 0x89, 'params': [1], 'comment': None},
    115: {'opcode': 0x8a, 'params': [0], 'comment': None},
    116: {'opcode': 0x8b, 'params': [1, 1, 1], 'comment': None},
    117: {'opcode': 0x8c, 'params': [1, 1, 1], 'comment': '(related to item acquisition sprite)'},
    118: {'opcode': 0x8d, 'params': [1, 1, 1, 1, 1, 1], 'comment': 'Play Wave-Warping Animation'},
    119: {'opcode': 0x8e, 'params': [1, 1, 1], 'comment': None},
    120: {'opcode': 0x8f, 'params': [1, 1, 1], 'comment': 'Wave motion up-down'},
    121: {'opcode': 0x90, 'params': [1, 1, 1], 'comment': 'Wave motion right-left'},
    122: {'opcode': 0x91, 'params': [1, 1], 'comment': None},
    123: {'opcode': 0x92, 'params': [1], 'comment': None},
    124: {'opcode': 0x94, 'params': [1, 1, 1], 'comment': None},
    125: {'opcode': 0x95, 'params': [1, 1, 1], 'comment': 'Screen tint animation'},
    126: {'opcode': 0x97, 'params': [0], 'comment': None},
    127: {'opcode': 0x98, 'params': [1, 1], 'comment': 'Thunder Warp'},
    128: {'opcode': 0x99, 'params': [1], 'comment': None},
    129: {'opcode': 0x9a, 'params': [1], 'comment': None},
    130: {'opcode': 0x9c, 'params': [1, 1, 1], 'comment': None},
    131: {'opcode': 0x9d, 'params': [1], 'comment': None},
    132: {'opcode': 0x9e, 'params': [4080], 'comment': None},
    133: {'opcode': 0x9f, 'params': [1, 1, 1], 'comment': 'Wave motion shrink'},
    134: {'opcode': 0xa0, 'params': [1, 1, 1, 1, 1, 1], 'comment': None},
    135: {'opcode': 0xa1, 'params': [1, 1], 'comment': None},
    136: {'opcode': 0xa2, 'params': [1], 'comment': None},
    137: {'opcode': 0xa3, 'params': [1, 1], 'comment': 'Play NPC focused animation'},
    138: {'opcode': 0xa4, 'params': [0], 'comment': 'Screen Mosaic'},
    139: {'opcode': 0xa5, 'params': [0], 'comment': 'Call Game Load Screen'},
    140: {'opcode': 0xa6, 'params': [0], 'comment': None},
    141: {'opcode': 0xa7, 'params': [1], 'comment': None},
    142: {'opcode': 0xa8, 'params': [1], 'comment': 'Ancient Cave Item Management'},
    143: {'opcode': 0xa9, 'params': [1, 1], 'comment': None},
    144: {'opcode': 0xaa, 'params': [0], 'comment': None},
    145: {'opcode': 0xab, 'params': [1], 'comment': 'Check Dragon Eggs Obtained'},
    146: {'opcode': 0xad, 'params': [1, 1, 1], 'comment': 'Dragon eggs related?'},
    147: {'opcode': 0xae, 'params': [1], 'comment': None},
    148: {'opcode': 0xaf, 'params': [1, 1], 'comment': 'Character Flicker'},
    149: {'opcode': 0xb0, 'params': [1], 'comment': None},
    150: {'opcode': 0xb1, 'params': [1, 1], 'comment': 'Character ???'},
    151: {'opcode': 0xb3, 'params': [1], 'comment': 'Party Members Change Facing'},
    152: {'opcode': 0xb4, 'params': [1, 1, 1], 'comment': None},
    153: {'opcode': 0xb5, 'params': [0], 'comment': None},
    154: {'opcode': 0xb6, 'params': [1, 1], 'comment': None},
    155: {'opcode': 0xb7, 'params': [1], 'comment': None},
    156: {'opcode': 0xb8, 'params': [0], 'comment': None},
    157: {'opcode': 0xb9, 'params': [1], 'comment': 'Fill IP Bar'},
    158: {'opcode': 0xba, 'params': [1], 'comment': None},
    159: {'opcode': 0xbb, 'params': [0], 'comment': 'Call game report'},
    160: {'opcode': 0xbc, 'params': [0], 'comment': None},
    161: {'opcode': 0xbd, 'params': [1, 1], 'comment': None},
    162: {'opcode': 0xbe, 'params': [1], 'comment': 'DUPLICATE - 77'},
    163: {'opcode': 0xbf, 'params': [1, 1, 1], 'comment': None},
    164: {'opcode': 0xc0, 'params': [1, 1, 1], 'comment': None},
    165: {'opcode': 0xc1, 'params': [1, 1], 'comment': None},
    166: {'opcode': 0xc2, 'params': [1, 1, 1, 1, 1, 1], 'comment': None},
    167: {'opcode': 0xc3, 'params': [1, 1, 1, 1, 1, 1], 'comment': None},
    168: {'opcode': 0xc4, 'params': [1, 1], 'comment': 'Scroll Screen'},
    169: {'opcode': 0xc5, 'params': [0], 'comment': None},
    170: {'opcode': 0xc6, 'params': [1, 1], 'comment': 'Play Sprite Animation'},
    171: {'opcode': 0xc7, 'params': [0], 'comment': None},
    172: {'opcode': 0xc9, 'params': [1, 1, 1, 1, 1, 1, 1], 'comment': None},
    173: {'opcode': 0xca, 'params': [1, 1, 1], 'comment': None},
    174: {'opcode': 0xcb, 'params': [1], 'comment': None},
    175: {'opcode': 0xcc, 'params': [0], 'comment': None}
}

