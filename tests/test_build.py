"""build() makes a ROM without the command line, and two builds in one process don't share state (Iris-Dev#5)."""

import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from iris.args import parse_args
from iris.build import Options, build
from iris.enums.patches import Patch
from iris.helpers import files
from iris.helpers.files import session, use
from iris.structures.monster import Monster
from iris.structures.shop import Shop
from iris.tables import select, selected


ROOT = Path(__file__).parent.parent
PLAIN = Options(1, selected_patch=Patch.VANILLA)
LOADED = Options(
    2,
    selected_patch=Patch.VANILLA,
    debug=True,
    debug_party=True,
    scale_encounters=(-5, 10),
    start_items=((2, 9), (64, 1)),
)


@pytest.fixture(autouse=True)
def _restore_session() -> Iterator[None]:
    """Give the rest of the suite back the session conftest opened."""
    rom, patch = session(), selected()
    verify_pointers, easy_mode = Shop.verify_pointers, Monster.easy_mode
    yield
    Shop.verify_pointers, Monster.easy_mode = verify_pointers, easy_mode
    select(patch)
    use(rom)


@pytest.fixture(scope="module")
def source() -> bytes:
    return files.original_file.read_bytes()


def test_builds_dont_leak_into_each_other(source: bytes) -> None:
    plain = build(source, PLAIN)
    loaded = build(source, LOADED)
    assert loaded != plain
    assert build(source, PLAIN) == plain


def test_build_matches_the_cli(source: bytes, tmp_path: Path) -> None:
    rom = tmp_path / "rom.smc"
    rom.write_bytes(source)
    argv = ["--file", str(rom), "--seed", "2", "--vanilla", "--debug", "--debug-party", "--scale-encounters", "-5", "10"]
    subprocess.run([sys.executable, "-m", "iris", *argv], cwd=ROOT, check=True, capture_output=True)  # noqa: S603
    cli = (tmp_path / "rom-2.smc").read_bytes()

    assert build(source, Options.from_args(parse_args(argv))) == cli


@pytest.mark.parametrize("base", ["--frue", "--spekkio", "--kureji"])
def test_every_base_patch_builds_with_debug(source: bytes, base: str) -> None:
    """FRUE-based ROMs ship some Absynnonym fixes already, and Kureji has no Pierre/Daniele: neither may fail a build."""
    build(source, Options.from_args(parse_args(["--file", "rom.smc", base, "--debug", "--debug-party"])))
