"""Build the overworld Archipelago base patch: vanilla ROM -> Iris build + AP asm -> bsdiff4 (Iris-Dev#6).

Every fixed change (Iris's own patches, the config block header, the AP item) is baked in here; the apworld only
writes seed-dependent bytes on top, as tokens. Run from the repo root::

    python tools/build_ap_basepatch.py --file <vanilla-rom>           # write archipelago/basepatch.bsdiff4
    python tools/build_ap_basepatch.py --file <vanilla-rom> --check   # exit 1 if the committed patch is stale

``--check`` applies the committed patch to the vanilla ROM and compares it with a fresh build, so it doesn't depend
on bsdiff4 producing the same diff twice. Needs the ``bsdiff4`` package.
"""

import argparse
import sys
from pathlib import Path

import bsdiff4


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from iris.api.rom import Rom
from iris.build import Options, build
from iris.enums.patches import Patch


PATCH_FILE = Path(__file__).resolve().parent.parent / "archipelago" / "basepatch.bsdiff4"
OPTIONS = Options(0, selected_patch=Patch.VANILLA, archipelago=True, unlock_warps=False)
"""Seed-independent: no randomizer runs, so the seed changes nothing."""


def vanilla_image(rom: Path) -> bytes:
    """The headerless vanilla ROM, the bytes players' ROMs are patched from."""
    return bytes(Rom.open(rom).image)


def build_patch(vanilla: bytes) -> bytes:
    return bsdiff4.diff(vanilla, build(vanilla, OPTIONS))


def is_current(vanilla: bytes, patch: bytes) -> bool:
    """True if ``patch`` turns ``vanilla`` into exactly what Iris builds now."""
    return bsdiff4.patch(vanilla, patch) == build(vanilla, OPTIONS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--file", type=Path, required=True, help="The vanilla US ROM (headered or not).")
    parser.add_argument("--check", action="store_true", help="Fail if the committed patch is stale.")
    args = parser.parse_args()
    vanilla = vanilla_image(args.file)

    if args.check:
        if PATCH_FILE.exists() and is_current(vanilla, PATCH_FILE.read_bytes()):
            print(f"{PATCH_FILE.name} is current.")
            return 0
        print(f"{PATCH_FILE.name} is stale: run tools/build_ap_basepatch.py --file <rom> and commit it.")
        return 1

    PATCH_FILE.write_bytes(build_patch(vanilla))
    print(f"Wrote {PATCH_FILE} ({PATCH_FILE.stat().st_size} bytes).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
