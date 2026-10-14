# ruff: noqa: T201, INP001 - a command-line script: printing is its output, and tests/emulator isn't a package.
"""Build a check ROM for ``start_vehicles.lua`` (Iris-Dev#16, #24).

A debug build whose new game starts in Elcid past the intro with a vehicle: ``jade``, ``engine`` or ``both`` for
standalone Iris's ``start_mermaid_jade``/``start_engine``, or ``ap`` for the overworld Archipelago base patch with both
config-block start bytes set to 1, as the apworld writes them (``ap-jade``, ``ap-engine``: one of them). Run from
``iris/``::

    uv run python tests/emulator/build_start_vehicles_rom.py <vanilla rom> <out.sfc> jade|engine|both|ap|ap-jade|ap-engine
    Mesen.exe --testRunner <out.sfc> tests/emulator/start_vehicles.lua
"""

import sys
from pathlib import Path


sys.path[:0] = [str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parents[2] / "src")]

from iris.args import parse_args
from iris.build import Options, build
from iris.constants import AP_OPT_START_ENGINE, AP_OPT_START_MERMAID_JADE
from iris.enums.patches import Patch
from iris.helpers.files import output_bytes, write_file


ALWAYS_DROP_33 = 0xFB55
"""``CMP $09FB`` at $81:FB55; the ALWAYS_DROP_33 code (which freezes item drops) would make it ``BRA``."""

AP_STARTS = {
    "ap": (AP_OPT_START_MERMAID_JADE, AP_OPT_START_ENGINE),
    "ap-jade": (AP_OPT_START_MERMAID_JADE,),
    "ap-engine": (AP_OPT_START_ENGINE,),
}
"""The config-block start bytes the apworld sets to 1, per AP kind."""


def main() -> None:
    source, out, kind = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    parse_args(["--file", str(source), "--vanilla", "--debug", "--debug-party"])
    options = Options(
        1,
        selected_patch=Patch.VANILLA,
        debug=True,
        debug_party=True,
        skip_intro=True,
        start_mermaid_jade=kind in {"jade", "both"},
        start_engine=kind in {"engine", "both"},
        archipelago=kind.startswith("ap"),
    )
    build(source, options)
    for offset in AP_STARTS.get(kind, ()):
        write_file.seek(offset)
        write_file.write(b"\x01")
    rom = output_bytes()
    assert rom[ALWAYS_DROP_33 : ALWAYS_DROP_33 + 3] == bytes.fromhex("CD FB 09"), "ALWAYS_DROP_33 is in"
    out.write_bytes(rom)
    print("wrote", out)


if __name__ == "__main__":
    main()
