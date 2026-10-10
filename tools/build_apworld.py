"""Zip archipelago/lufia2ow into lufia2ow.apworld, for Archipelago's custom_worlds folder.

Run tools/build_ap_basepatch.py and tools/export_ap_data.py first (or with --check) so the vendored base patch and data
are current. Usage::

    python tools/build_apworld.py [--out DIR] [--install ARCHIPELAGO_DIR]
"""

import argparse
import shutil
import zipfile
from pathlib import Path


WORLD = Path(__file__).resolve().parent.parent / "archipelago" / "lufia2ow"
SKIP = {"__pycache__"}


def build(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{WORLD.name}.apworld"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(WORLD.rglob("*")):
            if path.is_file() and not SKIP & set(path.parts):
                archive.write(path, Path(WORLD.name) / path.relative_to(WORLD))
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=WORLD.parent / "dist", help="Where to write the .apworld.")
    parser.add_argument("--install", type=Path, help="An Archipelago install; the .apworld is copied to its custom_worlds.")
    args = parser.parse_args()
    target = build(args.out)
    print(f"Wrote {target}.")  # noqa: T201
    if args.install:
        installed = shutil.copy2(target, args.install / "custom_worlds" / target.name)
        print(f"Installed {installed}.")  # noqa: T201


if __name__ == "__main__":
    main()
