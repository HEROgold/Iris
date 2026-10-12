"""The committed Archipelago base patch and data module match what Iris builds now (Iris-Dev#6, #7)."""

import importlib.util
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

from iris.build import Options
from iris.constants import AP_CONFIG_MAGIC, AP_CONFIG_MAGIC_OFFSET, AP_CONFIG_VERSION, AP_CONFIG_VERSION_OFFSET
from iris.helpers import files
from iris.helpers.files import session, use
from iris.patches.open_world.bosses import (
    BOSS_BATTLE,
    DAOS,
    FINAL_SPOT,
    ITEM,
    LOAD_NPC,
    MUSIC,
    SPOTS,
    fixed_placement,
)
from iris.tables import select, selected


bsdiff4 = pytest.importorskip("bsdiff4")

from tools.build_ap_basepatch import PATCHES, PATCH_FILE, OPEN_WORLD_PATCH_FILE, is_current, vanilla_image  # noqa: E402
from tools.export_ap_data import MODULES, OPEN_WORLD_DATA_FILE, render  # noqa: E402

patches = pytest.mark.parametrize(("patch_file", "options"), PATCHES, ids=lambda value: getattr(value, "name", ""))
modules = pytest.mark.parametrize(("data_file", "options"), MODULES, ids=lambda value: getattr(value, "name", ""))


@pytest.fixture
def vanilla() -> Iterator[bytes]:
    """The vanilla image, with the vanilla tables; conftest's session comes back afterwards."""
    rom, patch = session(), selected()
    image = vanilla_image(files.original_file)
    yield image
    select(patch)
    use(rom)


@patches
def test_basepatch_is_current(vanilla: bytes, patch_file: Path, options: Options) -> None:
    assert is_current(vanilla, patch_file.read_bytes(), options), "rerun tools/build_ap_basepatch.py and commit it"


@patches
def test_basepatch_writes_the_config_header(vanilla: bytes, patch_file: Path, options: Options) -> None:  # noqa: ARG001
    patched = bsdiff4.patch(vanilla, patch_file.read_bytes())
    assert patched[AP_CONFIG_MAGIC_OFFSET : AP_CONFIG_MAGIC_OFFSET + len(AP_CONFIG_MAGIC)] == AP_CONFIG_MAGIC
    assert patched[AP_CONFIG_VERSION_OFFSET] == AP_CONFIG_VERSION


def test_basepatch_keeps_the_copy_protection_happy_with_32kb_sram(vanilla: bytes) -> None:
    """The boot check compares $70:0000 with its 8KB mirror $70:2000; with 32KB of SRAM it must use $71:0000, or the
    game resets right after the logos."""
    patched = bsdiff4.patch(vanilla, PATCH_FILE.read_bytes())
    assert patched[0x7FD8] == 0x05  # 32KB SRAM
    for offset in (0x009A, 0x00A6):  # $80:809A, $80:80A6
        assert vanilla[offset : offset + 4] == bytes.fromhex("cf002070")  # CMP $702000
        assert patched[offset : offset + 4] == bytes.fromhex("cf000071")  # CMP $710000


@patches
def test_basepatch_code_stays_out_of_the_vram_graphics_bank(vanilla: bytes, patch_file: Path, options: Options) -> None:
    """Bank $9F from $8000 is DMA'd raw into VRAM; code asar's ``freecode`` put in its zero runs showed up as garbled
    item icons and battle tiles. Only the AP item's sprite ($9F:A900, 128 bytes) may change there, and no patch may
    leave a RATS tag (``freecode``) anywhere."""
    patched = bsdiff4.patch(vanilla, patch_file.read_bytes())
    bank, sprite = range(0x0F8000, 0x100000), range(0x0FA900, 0x0FA980)
    changed = [offset for offset in bank if offset not in sprite and patched[offset] != vanilla[offset]]
    assert not changed, f"bank $9F changed at {changed[0]:#x} ({len(changed)} bytes)"
    assert patched[: len(vanilla)].count(b"STAR") == vanilla.count(b"STAR"), "a freecode block landed in vanilla space"


@modules
def test_data_module_is_current(vanilla: bytes, data_file: Path, options: Options) -> None:
    assert data_file.read_text(encoding="utf-8") == render(vanilla, options), "rerun tools/export_ap_data.py, commit it"


def _load(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_boss_npc_operands_read_back(vanilla: bytes) -> None:
    """Every exported boss operand offset holds the expected byte in the open-world base ROM."""
    data = _load(OPEN_WORLD_DATA_FILE)
    patched = bsdiff4.patch(vanilla, OPEN_WORLD_PATCH_FILE.read_bytes())
    bosses = {boss[0]: boss for boss in [*data.BOSSES, data.DAOS]}
    spots = {spot[0]: spot for spot in [*data.BOSS_SPOTS, data.FINAL_SPOT]}
    assert [npc[0] for npc in data.BOSS_NPCS] == [*spots]
    placement = fixed_placement()
    for name, map_index, _, signature, sprite, bgm, formation, rewards in data.BOSS_NPCS:
        spot = next(spot for spot in [*SPOTS, FINAL_SPOT] if spot.name == name)
        boss = DAOS if spot is FINAL_SPOT else placement[spot]
        _, boss_sprite, boss_formation, boss_bgm = bosses[boss.name]
        assert map_index == spot.map_index
        slot = int(signature.split("-")[2], 16)
        assert patched[sprite - 2 : sprite + 1] == bytes([LOAD_NPC, slot, boss_sprite])
        assert patched[bgm - 1 : bgm + 1] == bytes([MUSIC, boss_bgm])
        assert patched[formation - 1 : formation + 1] == bytes([BOSS_BATTLE, boss_formation])
        assert len(rewards) == spots[name][2]
        for offset in rewards:
            assert patched[offset - 1 : offset + 2] == bytes([ITEM, data.PLACEHOLDER_ITEM, 1])


@modules
def test_data_module_imports_without_iris(data_file: Path, options: Options) -> None:  # noqa: ARG001
    """Isolated mode, no PYTHONPATH: the module needs nothing but the standard interpreter."""
    code = (
        "import importlib.util, sys; spec = importlib.util.spec_from_file_location('data', sys.argv[1]); "
        "module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); "
        "assert len(module.CHESTS) == 171 and module.GOAL_FLAG == 115"
    )
    subprocess.run([sys.executable, "-I", "-c", code, str(data_file)], check=True)  # noqa: S603
