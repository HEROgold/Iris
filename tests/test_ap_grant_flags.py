"""Every script grant outside the Ancient Cave sets a flag in the Archipelago base patches (Iris-Dev#22).

A grant is an AP location only when its script sets a flag: the client reports the location once that flag is set.
The rows are ``GRANTS`` as ``tools/export_ap_data`` exports them for each base patch.
"""

from collections.abc import Iterator

import pytest

from iris.build import Options, build
from iris.enums.patches import Patch
from iris.helpers import files
from iris.helpers.files import open_rom, session, use
from iris.patches.archipelago.overworld.grant_flags import FLAGGED_GRANTS, GRANT_OPS, SET_FLAG
from iris.structures.event_script import MapEvent
from iris.structures.event_script.containers import reset_map_events
from iris.structures.event_script.dump import _signature
from iris.tables import select, selected


pytest.importorskip("bsdiff4")

from tools.build_ap_basepatch import OPEN_WORLD_OPTIONS, OPTIONS, vanilla_image  # noqa: E402
from tools.export_ap_data import _grants, _moved, _script  # noqa: E402


ANCIENT_CAVE_MAPS = frozenset((0xEF, 0xF0, 0xF1))
"""Its grants (the Ancient key) aren't locations: ``lufia2ow.logic.EXCLUDED_MAPS``."""


@pytest.fixture
def restore() -> Iterator[None]:
    rom, patch = session(), selected()
    yield
    select(patch)
    use(rom)


def _unflagged(options: Options) -> list[str]:
    """The exported grants outside the Ancient Cave whose flags aren't all set by their own script in the build."""
    image = vanilla_image(files.original_file)
    select(Patch.VANILLA)
    open_rom(image)
    vanilla = _grants()
    build(image, options)
    out = []
    for map_index, signature, _, item, _, flags in _moved(vanilla, open_world=options.open_world):
        if map_index in ANCIENT_CAVE_MAPS:
            continue
        sets = {ins.operands[0] for ins in _script(map_index, signature).instructions if ins.opcode == SET_FLAG}
        if not flags or not set(flags) <= sets:
            out.append(f"{signature} item {item} flags {flags}")
    return out


def _flag_after_grant(map_index: int, signature: str, item: int) -> int | None:
    """The flag a ``1A`` right after the grant of ``item`` sets; ``None`` when the script doesn't grant it."""
    map_event = MapEvent.from_index(map_index)
    map_event.read()
    script = next(
        script
        for event_list in map_event.event_lists
        for script in event_list.events
        if _signature(map_index, script) == signature
    )
    for grant, after in zip(script.instructions, script.instructions[1:], strict=False):
        operand = grant.operands[0] if grant.opcode in GRANT_OPS else None
        if isinstance(operand, int) and GRANT_OPS[grant.opcode] + operand == item:
            assert after.opcode == SET_FLAG, f"{signature}: no flag after the grant"
            flag = after.operands[0]
            assert isinstance(flag, int)
            return flag
    return None


@pytest.mark.usefixtures("restore")
@pytest.mark.parametrize("options", [OPTIONS, OPEN_WORLD_OPTIONS], ids=["linear", "open_world"])
def test_every_grant_sets_a_flag(options: Options) -> None:
    assert not _unflagged(options)


@pytest.mark.usefixtures("restore")
def test_linear_grants_set_their_new_flag() -> None:
    build(vanilla_image(files.original_file), OPTIONS)
    reset_map_events()
    for grant in FLAGGED_GRANTS:
        assert _flag_after_grant(grant.map_index, grant.signature, grant.item) == grant.flag


@pytest.mark.usefixtures("restore")
def test_open_world_ear_jewel_sets_its_flag() -> None:
    """Open world keeps the Ear jewel grant; its Merix egg and Engine scripts grant nothing."""
    build(vanilla_image(files.original_file), OPEN_WORLD_OPTIONS)
    reset_map_events()
    found = {grant.signature: _flag_after_grant(grant.map_index, grant.signature, grant.item) for grant in FLAGGED_GRANTS}
    ear_jewel, merix_egg, engine = FLAGGED_GRANTS
    assert found == {ear_jewel.signature: ear_jewel.flag, merix_egg.signature: None, engine.signature: None}
