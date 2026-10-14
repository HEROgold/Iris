# ruff: noqa: T201, INP001 - a command-line script: printing is its output, and tests/emulator isn't a package.
"""Build a check ROM for ``encounter_scaling.lua`` (Iris-Dev#25).

A debug build with the overworld Archipelago base patch, whose new game starts in Elcid past the intro. ``off`` keeps
the base patch's config bytes (scaling off); ``on LOW HIGH`` writes them as the apworld does (on, LOW in two's
complement, HIGH - LOW + 1). Run from ``iris/``::

    uv run python tests/emulator/build_encounter_scaling_rom.py <vanilla rom> <out.sfc> off|on [LOW HIGH]
    Mesen.exe --testRunner <out.sfc> tests/emulator/encounter_scaling.lua
"""

import sys
from pathlib import Path


sys.path[:0] = [str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parents[2] / "src")]

from iris.args import parse_args
from iris.build import Options, build
from iris.constants import AP_OPT_SCALING_ENABLED, AP_OPT_SCALING_LOW, AP_OPT_SCALING_RANGE
from iris.enums.patches import Patch
from iris.helpers.files import output_bytes, write_file


ALWAYS_DROP_33 = 0xFB55
"""``CMP $09FB`` at $81:FB55; the ALWAYS_DROP_33 code (which freezes item drops) would make it ``BRA``."""


def main() -> None:
    source, out, kind = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    parse_args(["--file", str(source), "--vanilla", "--debug", "--debug-party"])
    options = Options(1, selected_patch=Patch.VANILLA, debug=True, debug_party=True, skip_intro=True, archipelago=True)
    build(source, options)
    if kind == "on":
        low, high = int(sys.argv[4]), int(sys.argv[5])
        for offset, value in (
            (AP_OPT_SCALING_ENABLED, 1),
            (AP_OPT_SCALING_LOW, low.to_bytes(1, "little", signed=True)[0]),
            (AP_OPT_SCALING_RANGE, high - low + 1),
        ):
            write_file.seek(offset)
            write_file.write(bytes([value]))
    rom = output_bytes()
    assert rom[ALWAYS_DROP_33 : ALWAYS_DROP_33 + 3] == bytes.fromhex("CD FB 09"), "ALWAYS_DROP_33 is in"
    out.write_bytes(rom)
    print("wrote", out, "scaling", rom[AP_OPT_SCALING_ENABLED], rom[AP_OPT_SCALING_LOW], rom[AP_OPT_SCALING_RANGE])


if __name__ == "__main__":
    main()
