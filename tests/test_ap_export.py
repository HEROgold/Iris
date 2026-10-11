"""The committed Archipelago base patch and data module match what Iris builds now (Iris-Dev#6, #7)."""

import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from iris.constants import AP_CONFIG_MAGIC, AP_CONFIG_MAGIC_OFFSET, AP_CONFIG_VERSION, AP_CONFIG_VERSION_OFFSET
from iris.helpers import files
from iris.helpers.files import session, use
from iris.tables import select, selected


bsdiff4 = pytest.importorskip("bsdiff4")

from tools.build_ap_basepatch import PATCH_FILE, is_current, vanilla_image  # noqa: E402
from tools.export_ap_data import DATA_FILE, render  # noqa: E402


@pytest.fixture
def vanilla() -> Iterator[bytes]:
    """The vanilla image, with the vanilla tables; conftest's session comes back afterwards."""
    rom, patch = session(), selected()
    image = vanilla_image(files.original_file)
    yield image
    select(patch)
    use(rom)


def test_basepatch_is_current(vanilla: bytes) -> None:
    assert is_current(vanilla, PATCH_FILE.read_bytes()), "rerun tools/build_ap_basepatch.py and commit the patch"


def test_basepatch_writes_the_config_header(vanilla: bytes) -> None:
    patched = bsdiff4.patch(vanilla, PATCH_FILE.read_bytes())
    assert patched[AP_CONFIG_MAGIC_OFFSET : AP_CONFIG_MAGIC_OFFSET + len(AP_CONFIG_MAGIC)] == AP_CONFIG_MAGIC
    assert patched[AP_CONFIG_VERSION_OFFSET] == AP_CONFIG_VERSION


def test_data_module_is_current(vanilla: bytes) -> None:
    assert DATA_FILE.read_text(encoding="utf-8") == render(vanilla), "rerun tools/export_ap_data.py and commit the module"


def test_data_module_imports_without_iris() -> None:
    """Isolated mode, no PYTHONPATH: the module needs nothing but the standard interpreter."""
    code = (
        "import importlib.util, sys; spec = importlib.util.spec_from_file_location('data', sys.argv[1]); "
        "module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); "
        "assert len(module.CHESTS) == 171 and module.GOAL_FLAG == 115"
    )
    subprocess.run([sys.executable, "-I", "-c", code, str(Path(DATA_FILE))], check=True)  # noqa: S603
