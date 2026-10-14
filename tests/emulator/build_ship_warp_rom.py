# ruff: noqa: T201, INP001 - a command-line script: printing is its output, and tests/emulator isn't a package.
"""Build the check ROM for ``ship_warp.lua`` (Iris-Dev#51).

A debug build with the overworld Archipelago base patch: a new game starts in Elcid past the intro, every Warp
destination open, Maxim knowing Warp and a Progressive Ship in the bag (the field loop turns it into the Ship). Run
from ``iris/``::

    uv run python tests/emulator/build_ship_warp_rom.py <vanilla rom> <out.sfc>
    Mesen.exe --testRunner <out.sfc> tests/emulator/ship_warp.lua
"""

import sys
from pathlib import Path


sys.path[:0] = [str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parents[2] / "src")]

from iris.args import parse_args
from iris.build import Options, build
from iris.enums.patches import Patch
from iris.helpers.files import output_bytes
from iris.patches.archipelago.overworld.key_items import PROGRESSIVE_SHIP


def main() -> None:
    source, out = Path(sys.argv[1]), Path(sys.argv[2])
    parse_args(["--file", str(source), "--vanilla"])
    options = Options(
        1,
        selected_patch=Patch.VANILLA,
        debug=True,
        debug_party=True,
        skip_intro=True,
        archipelago=True,
        start_items=((PROGRESSIVE_SHIP, 1),),
    )
    build(source, options)
    from iris.patches.HEROgold.maxim_warp import maxim_starts_with_warp  # noqa: PLC0415 - lookups read the ROM on import

    maxim_starts_with_warp()
    out.write_bytes(output_bytes())
    print("wrote", out)


if __name__ == "__main__":
    main()
