# ruff: noqa: T201, INP001 - a command-line script: printing is its output, and tests/emulator isn't a package.
"""Build a check ROM for ``scenario_items.lua`` (Iris-Dev#26).

A debug build with the overworld Archipelago base patch, whose new game starts in Elcid past the intro, with the
scenario-item mode byte set to MODE (0 vanilla removals, 1 no removals). The debug build's NO_SCENARIO_ITEMS code is
undone: it makes every scenario item count as held, which the check needs to see. Run from ``iris/``::

    uv run python tests/emulator/build_scenario_items_rom.py <vanilla rom> <out.sfc> 0|1
    Mesen.exe --testRunner <out.sfc> tests/emulator/scenario_items.lua
"""

import sys
from pathlib import Path


sys.path[:0] = [str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parents[2] / "src")]

from iris.args import parse_args
from iris.build import Options, build
from iris.constants import AP_OPT_SCENARIO_ITEM_MODE
from iris.enums.patches import Patch
from iris.helpers.files import output_bytes, write_file


ALWAYS_DROP_33 = 0xFB55
"""``CMP $09FB`` at $81:FB55; the ALWAYS_DROP_33 code (which freezes item drops) would make it ``BRA``."""
NO_SCENARIO_ITEMS = 0x017B80
"""$82:FB80: ``AND $091E,Y`` in the held? lookup ($39); NO_SCENARIO_ITEMS makes it ``RTS`` ($60)."""
VANILLA_AND, RTS = 0x39, 0x60


def main() -> None:
    source, out, mode = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
    parse_args(["--file", str(source), "--vanilla", "--debug", "--debug-party"])
    options = Options(1, selected_patch=Patch.VANILLA, debug=True, debug_party=True, skip_intro=True, archipelago=True)
    build(source, options)
    write_file.seek(NO_SCENARIO_ITEMS)
    assert write_file.read(1)[0] in (VANILLA_AND, RTS)
    write_file.seek(NO_SCENARIO_ITEMS)
    write_file.write(bytes([VANILLA_AND]))
    write_file.seek(AP_OPT_SCENARIO_ITEM_MODE)
    write_file.write(bytes([mode]))
    rom = output_bytes()
    assert rom[ALWAYS_DROP_33 : ALWAYS_DROP_33 + 3] == bytes.fromhex("CD FB 09"), "ALWAYS_DROP_33 is in"
    assert rom[NO_SCENARIO_ITEMS] == VANILLA_AND, "NO_SCENARIO_ITEMS is in"
    out.write_bytes(rom)
    print("wrote", out, "mode", rom[AP_OPT_SCENARIO_ITEM_MODE])


if __name__ == "__main__":
    main()
