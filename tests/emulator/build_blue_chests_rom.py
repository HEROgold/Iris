# ruff: noqa: T201, INP001 - a command-line script: printing is its output, and tests/emulator isn't a package.
"""Build a check ROM for ``blue_chests.lua`` (Iris-Dev#21).

A debug build with the overworld Archipelago base patch, whose new game starts in Elcid past the intro, with the
blue-chest config bytes set to COUNT (0 = off), plus the test-only ``blue_chests_harness.asm``, which lets Lua open a
chest, save or load a slot from the field main loop. Run from ``iris/``::

    uv run python tests/emulator/build_blue_chests_rom.py <vanilla rom> <out.sfc> <count>
    Mesen.exe --testRunner <out.sfc> tests/emulator/blue_chests.lua
"""

import sys
from pathlib import Path


sys.path[:0] = [str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parents[2] / "src")]

from iris.args import parse_args
from iris.build import Options, build
from iris.constants import AP_OPT_BLUE_CHESTS_ENABLED
from iris.enums.patches import Patch
from iris.helpers.addresses import address_from_lorom
from iris.helpers.files import output_bytes
from iris.patcher import apply_asm_patch
from iris.patches.archipelago.overworld.blue_chests import write_blue_chests


ALWAYS_DROP_33 = 0xFB55
"""``CMP $09FB`` at $81:FB55; the ALWAYS_DROP_33 code (which freezes item drops) would make it ``BRA``."""
HARNESS = Path(__file__).parent / "blue_chests_harness.asm"
HARNESS_REGION = range(0x341C00, 0x341D00)
"""Blank expansion space past BLUE_CHESTS_CODE_REGION; only check ROMs use it."""
MAIN_LOOP_SITE, SAVE_SITE, LOAD_SITE = 0x01BC16, 0x016B61, 0x016AD5
"""$83:BC16, $82:EB61, $82:EAD5: rx.asm's JSLs to MainLoop, SaveRX and LoadRX."""


def _jsl_target(rom: bytes, site: int) -> str:
    assert rom[site] == 0x22
    return f"${int.from_bytes(rom[site + 1:site + 4], 'little'):06X}"


def main() -> None:
    source, out, count = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
    parse_args(["--file", str(source), "--vanilla", "--debug", "--debug-party"])
    options = Options(1, selected_patch=Patch.VANILLA, debug=True, debug_party=True, skip_intro=True, archipelago=True)
    rom = build(source, options)
    defines = {name: _jsl_target(rom, site) for name, site in
               (("main_loop", MAIN_LOOP_SITE), ("save_rx", SAVE_SITE), ("load_rx", LOAD_SITE))}
    apply_asm_patch(HARNESS, defines=defines, code_region=HARNESS_REGION)
    write_blue_chests(count)
    rom = output_bytes()
    assert rom[ALWAYS_DROP_33 : ALWAYS_DROP_33 + 3] == bytes.fromhex("CD FB 09"), "ALWAYS_DROP_33 is in"
    assert address_from_lorom(int(defines["main_loop"][1:], 16)) < HARNESS_REGION.start
    out.write_bytes(rom)
    enabled, low, high = rom[AP_OPT_BLUE_CHESTS_ENABLED:AP_OPT_BLUE_CHESTS_ENABLED + 3]
    print("wrote", out, "blue chests enabled", enabled, "count", low | high << 8, defines)


if __name__ == "__main__":
    main()
