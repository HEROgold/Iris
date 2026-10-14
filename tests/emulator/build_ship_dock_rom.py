# ruff: noqa: T201, INP001 - a command-line script: printing is its output, and tests/emulator isn't a package.
"""Build a check ROM for ``ship_dock.lua`` (Iris-Dev#67).

A debug build with the overworld Archipelago base patch and no ship: a new game starts in Elcid past the intro, or with
``treadool`` in Treadool, linear or with ``open`` open world. ``ship_dock.lua`` receives the Ship there the way the
client does. Run from ``iris/``::

    uv run python tests/emulator/build_ship_dock_rom.py <vanilla rom> <out.sfc> [elcid|treadool] [open]
    Mesen.exe --testRunner <out.sfc> tests/emulator/ship_dock.lua
"""

import sys
from pathlib import Path


sys.path[:0] = [str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parents[2] / "src")]

from iris.args import parse_args
from iris.build import Options, build
from iris.enums.patches import Patch
from iris.helpers.files import output_bytes, write_file


TREADOOL = 0x7A
TREADOOL_ENTRANCE = 0x02
SPAWN_MAP = 0x01ADAC
"""The operand of the new game's ``LDA #map`` (patcher.set_spawn_location; skip_intro already moved it off vanilla)."""
SPAWN_ENTRANCE = 0x01ADB4


def main() -> None:
    source, out = Path(sys.argv[1]), Path(sys.argv[2])
    town = sys.argv[3] if len(sys.argv) > 3 else "elcid"  # noqa: PLR2004 - the optional third argument
    parse_args(["--file", str(source), "--vanilla"])
    options = Options(
        1,
        selected_patch=Patch.VANILLA,
        debug=True,
        debug_party=True,
        skip_intro=True,
        archipelago=True,
        open_world="open" in sys.argv[4:],
    )
    build(source, options)
    if town == "treadool":
        from iris.structures.zone import Zone  # noqa: PLC0415 - zones read the ROM on import

        assert TREADOOL_ENTRANCE in {entrance.cutscene for entrance in Zone.from_index(TREADOOL).valid_entrances}
        write_file.seek(SPAWN_MAP)
        write_file.write(bytes([TREADOOL]))
        write_file.seek(SPAWN_ENTRANCE)
        write_file.write(bytes([TREADOOL_ENTRANCE]))
    out.write_bytes(output_bytes())
    print("wrote", out)


if __name__ == "__main__":
    main()
