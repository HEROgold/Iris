"""The open-world extras and leaders are per-seed byte diffs over the AP base patch, and they compose (Iris-Dev#43).

The world writes the chosen extras' runs (``data_open_world.EXTRA_DIFFS``), the leader's and the leader's runs inside
the chosen extras' scripts over the base ROM. That has to equal what Iris builds with all of them on.
"""

import importlib.util
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from types import ModuleType

import pytest

from iris.build import build
from iris.helpers import files
from iris.helpers.files import session, use
from iris.tables import select, selected


bsdiff4 = pytest.importorskip("bsdiff4")

from tools.build_ap_basepatch import OPEN_WORLD_OPTIONS, OPEN_WORLD_PATCH_FILE, vanilla_image  # noqa: E402
from tools.export_ap_data import CHECKSUM, OPEN_WORLD_DATA_FILE, apply_runs  # noqa: E402


def _load(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DATA = _load(OPEN_WORLD_DATA_FILE)
ALL_EXTRAS = tuple(extra for extra in DATA.EXTRAS if extra != "npc_cave_bridge_orb_guard")
"""Every extra but the orb guard, which can't go with orb_check."""
WITH_GUARD = tuple(extra for extra in DATA.EXTRAS if extra != "orb_check")


@pytest.fixture(scope="module")
def vanilla() -> Iterator[bytes]:
    rom, patch = session(), selected()
    yield vanilla_image(files.original_file)
    select(patch)
    use(rom)


@pytest.fixture(scope="module")
def base(vanilla: bytes) -> bytes:
    return bsdiff4.patch(vanilla, OPEN_WORLD_PATCH_FILE.read_bytes())


def _composed(base: bytes, extras: tuple[str, ...], leader: str | None) -> bytes:
    runs = [DATA.EXTRA_DIFFS[extra] for extra in DATA.EXTRAS if extra in extras]
    if leader is not None:
        runs.append(DATA.LEADER_DIFFS[leader])
        runs += [DATA.LEADER_EXTRA_DIFFS[leader, extra] for extra in extras if (leader, extra) in DATA.LEADER_EXTRA_DIFFS]
    return apply_runs(base, *runs)


def _differences(a: bytes, b: bytes) -> list[int]:
    return [offset for offset, (x, y) in enumerate(zip(a, b, strict=True)) if x != y and offset not in CHECKSUM]


@pytest.mark.parametrize("extras", [ALL_EXTRAS, WITH_GUARD], ids=["orb_check", "orb_guard"])
@pytest.mark.parametrize("leader", [None, *DATA.LEADERS])
def test_variants_compose(vanilla: bytes, base: bytes, extras: tuple[str, ...], leader: str | None) -> None:
    options = replace(OPEN_WORLD_OPTIONS, open_world_extras=extras, leader=DATA.LEADERS[leader] if leader else None)
    built = build(vanilla, options)
    wrong = _differences(_composed(base, extras, leader), built)
    assert not wrong, f"{len(wrong)} bytes differ, the first at {wrong[0]:#x}"


@pytest.mark.parametrize("extra", DATA.EXTRAS)
def test_each_extra_alone(vanilla: bytes, base: bytes, extra: str) -> None:
    built = build(vanilla, replace(OPEN_WORLD_OPTIONS, open_world_extras=(extra,)))
    assert not _differences(_composed(base, (extra,), None), built)


def test_variants_are_small() -> None:
    """In place: no extra or leader moves a container, so each stays a few KB at most."""
    sizes = {name: sum(len(data) // 2 for _, data in runs) for name, runs in {**DATA.EXTRA_DIFFS, **DATA.LEADER_DIFFS}.items()}
    assert max(sizes.values()) < 0x2000, sizes


def test_orb_check_grant(base: bytes) -> None:
    """The orb check's item byte is a grant (opcode 0x20) once orb_check's runs are written, and not before."""
    map_index, offset, item, flag = DATA.ORB_CHECK
    rom = _composed(base, ("orb_check",), None)
    assert (map_index, flag) == (0x44, 0x30)
    assert rom[offset - 1 : offset + 1] == bytes([0x20, item])
    assert base[offset - 1 : offset + 1] != rom[offset - 1 : offset + 1]
