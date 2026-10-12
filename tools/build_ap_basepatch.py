"""Build the overworld Archipelago base patches: vanilla ROM -> Iris build + AP asm -> bsdiff4 (Iris-Dev#6, #43).

Every fixed change (Iris's own patches, the config block header, the AP item) is baked in here; the apworld only
writes seed-dependent bytes on top, as tokens. There are two: the linear game (``basepatch.bsdiff4``) and open world
(``basepatch_open_world.bsdiff4``: fixed boss placement, no extras, no leader, boss strength set by the world's tokens).
Run from the repo root::

    python tools/build_ap_basepatch.py --file <vanilla-rom>           # write both patches to ../lufia2ow/
    python tools/build_ap_basepatch.py --file <vanilla-rom> --check   # exit 1 if a committed patch is stale

``--check`` applies the committed patch to the vanilla ROM and compares it with a fresh build, so it doesn't depend
on bsdiff4 producing the same diff twice. Needs the ``bsdiff4`` package.
"""

import argparse
import hashlib
import sys
from dataclasses import replace
from pathlib import Path

import bsdiff4


sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[1] / "src")]

from iris.api.rom import CART_SIZE_20MBIT, Rom
from iris.build import Options, build
from iris.enums.patches import Patch


WORLD_DIR = Path(__file__).resolve().parents[2] / "lufia2ow"
"""The lufia2ow world, the submodule next to this repo in Iris-Dev."""
PATCH_FILE = WORLD_DIR / "basepatch.bsdiff4"
OPEN_WORLD_PATCH_FILE = WORLD_DIR / "basepatch_open_world.bsdiff4"
US_MD5 = "6efc477d6203ed2b3b9133c1cd9e9c5d"
"""The headerless 2.5MB US ROM (No-Intro), the bytes Archipelago players patch."""
OPTIONS = Options(0, selected_patch=Patch.VANILLA, archipelago=True, unlock_warps=False)
"""Seed-independent: no randomizer runs, so the seed changes nothing."""
OPEN_WORLD_OPTIONS = replace(OPTIONS, open_world=True, boss_placement="fixed")
"""Open world with the fixed boss placement; the world's tokens move bosses and set their strength per seed."""
PATCHES = ((PATCH_FILE, OPTIONS), (OPEN_WORLD_PATCH_FILE, OPEN_WORLD_OPTIONS))


def vanilla_image(rom: Path) -> bytes:
    """The headerless 2.5MB US ROM, from a headered, headerless or 3MB (repeated last half-megabyte) dump."""
    image = bytes(Rom.open(rom).image)[:CART_SIZE_20MBIT]
    if hashlib.md5(image).hexdigest() != US_MD5:  # noqa: S324 - identifies the ROM, not security
        msg = f"{rom} isn't the US Lufia II ROM (md5 of the headerless 2.5MB image should be {US_MD5})."
        raise ValueError(msg)
    return image


def build_patch(vanilla: bytes, options: Options = OPTIONS) -> bytes:
    return bsdiff4.diff(vanilla, build(vanilla, options))


def is_current(vanilla: bytes, patch: bytes, options: Options = OPTIONS) -> bool:
    """True if ``patch`` turns ``vanilla`` into exactly what Iris builds now with ``options``."""
    return bsdiff4.patch(vanilla, patch) == build(vanilla, options)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--file", type=Path, required=True, help="The vanilla US ROM (headered or not).")
    parser.add_argument("--check", action="store_true", help="Fail if the committed patch is stale.")
    args = parser.parse_args()
    vanilla = vanilla_image(args.file)

    if args.check:
        stale = 0
        for patch_file, options in PATCHES:
            if patch_file.exists() and is_current(vanilla, patch_file.read_bytes(), options):
                print(f"{patch_file.name} is current.")
            else:
                print(f"{patch_file.name} is stale: run tools/build_ap_basepatch.py --file <rom> and commit it.")
                stale += 1
        return 1 if stale else 0

    for patch_file, options in PATCHES:
        patch_file.write_bytes(build_patch(vanilla, options))
        print(f"Wrote {patch_file} ({patch_file.stat().st_size} bytes).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
