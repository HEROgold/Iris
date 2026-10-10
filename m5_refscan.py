"""Throwaway: find code references to each L2BASM table (HER-196 to HER-200). Not committed."""

import sys

ROM = open("roms/Lufia II - Rise of the Sinistrals (U) [!].smc", "rb").read()  # noqa: SIM115, PTH123
CODE_BANKS = range(0x00, 0x10)  # $80-$8F: where the game's code lives

TABLES = {
    "monster": 0xB05C0,
    "item": 0xB4F69,
    "ip_effect": 0xAF1EF,
    "spell": 0xAFA5B,
    "capsule": 0xBDCB8,
    "capattack": 0xBF63B,
}
LONG = {0xAF: "LDA l", 0xBF: "LDA l,X", 0x8F: "STA l", 0x9F: "STA l,X", 0xCF: "CMP l", 0xDF: "CMP l,X", 0x6F: "ADC l",
        0x7F: "ADC l,X", 0x2F: "AND l", 0x3F: "AND l,X", 0x0F: "ORA l", 0x1F: "ORA l,X", 0x4F: "EOR l", 0x5F: "EOR l,X",
        0xEF: "SBC l", 0xFF: "SBC l,X", 0x22: "JSL", 0x5C: "JML"}
IMM16 = {0x69: "ADC #", 0xA9: "LDA #", 0xA2: "LDX #", 0xA0: "LDY #", 0xC9: "CMP #", 0xE9: "SBC #", 0xE0: "CPX #",
         0xC0: "CPY #", 0x09: "ORA #", 0x29: "AND #", 0x49: "EOR #", 0xF4: "PEA"}
ABS = {0xAD: "LDA a", 0xBD: "LDA a,X", 0xB9: "LDA a,Y", 0xAE: "LDX a", 0xAC: "LDY a", 0xBE: "LDX a,Y", 0xBC: "LDY a,X",
       0x8D: "STA a", 0x9D: "STA a,X", 0x99: "STA a,Y", 0x6D: "ADC a", 0x7D: "ADC a,X", 0x79: "ADC a,Y", 0xCD: "CMP a",
       0xDD: "CMP a,X", 0xD9: "CMP a,Y"}


def lorom(address: int) -> int:
    return (0x80 + (address >> 15)) << 16 | 0x8000 | (address & 0x7FFF)


def scan(name: str, table: int, deltas: range) -> None:
    snes = lorom(table)
    bank = snes >> 16
    print(f"== {name} {table:#x} ${snes >> 16:02X}:{snes & 0xFFFF:04X}")  # noqa: T201
    for b in CODE_BANKS:
        lo, hi = b * 0x8000, (b + 1) * 0x8000
        for pos in range(lo + 1, hi - 3):
            op = ROM[pos - 1]
            for d in deltas:
                value = snes + d
                if op in LONG and ROM[pos : pos + 3] == value.to_bytes(3, "little"):
                    print(f"  {pos:#07x} {LONG[op]} ${value >> 16:02X}:{value & 0xFFFF:04X}  (d={d:+#x})  {ROM[pos - 6:pos + 6].hex(' ')}")  # noqa: T201
                if op in IMM16 | ABS and ROM[pos : pos + 2] == (value & 0xFFFF).to_bytes(2, "little"):
                    kind = IMM16.get(op) or ABS[op]
                    print(f"  {pos:#07x} {kind} ${value & 0xFFFF:04X}  (d={d:+#x})  {ROM[pos - 6:pos + 6].hex(' ')}")  # noqa: T201
    for b in CODE_BANKS:
        for pos in range(b * 0x8000, (b + 1) * 0x8000 - 1):
            if ROM[pos] == 0xA9 and ROM[pos + 1] == bank and ROM[pos + 2] in (0x48, 0x85, 0x8D, 0x8F):  # LDA #bank; PHA/STA
                print(f"  bank {pos + 1:#07x} LDA #${bank:02X} then {ROM[pos + 2]:02X}  {ROM[pos - 4:pos + 8].hex(' ')}")  # noqa: T201


for name in sys.argv[1:] or TABLES:
    scan(name, TABLES[name], range(-2, 0x30))
