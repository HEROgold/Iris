"""Story hand-ins test the item, not the grant's flag, in the linear Archipelago base patch (Iris-Dev#49).

A grant is an AP location: its flag only says the spot was checked, and the item can come from another world. So no
script that takes a scenario item from the party may decide to on the flag of that item's grant.
"""

import importlib.util
from collections.abc import Iterator
from types import ModuleType

import pytest

from iris import build as build_module
from iris.build import build
from iris.enums.patches import Patch
from iris.helpers import files
from iris.helpers.files import open_rom, session, use
from iris.enums.flags import EventFlag
from iris.patches.archipelago.overworld.hand_ins import ENGINE, HAND_INS, HandIn
from iris.structures.event_script import MapEvent
from iris.structures.event_script.containers import reset_map_events
from iris.structures.event_script.dump import _signature
from iris.structures.event_script.instructions import Address, Instruction, Operand
from iris.structures.event_script.script import EventScript
from iris.tables import MapEventObject, select, selected


pytest.importorskip("bsdiff4")

from tools.build_ap_basepatch import OPEN_WORLD_OPTIONS, OPTIONS, vanilla_image  # noqa: E402
from tools.export_ap_data import DATA_FILE  # noqa: E402


REMOVE_ITEM = {0x24: 0x000, 0x25: 0x100}
"""Opcode -> the item-number base its 1-byte operand adds to."""
FLAG_BRANCHES = (0x15, 0x6A)
"""Branch if the flag is set / not set: ``(flag, @target)``."""
CONDITION = 0x14
SET_FLAG = 0x1A
ENGINE_GRANT_CHAIN = ("D6-C-02", "A0-A-02", "90-A-01", "A0-A-03")
"""The Gratze grant and the warp chain after it, which ends in the scene that sets GOT_ENGINE."""
LEXIS_LAB = "A2-B-2C"
CHAIN_FLAG_CODES = frozenset((0x00, 0x01, 0x40, 0x41, 0x80, 0x81))
"""``0x14`` sub-codes that test a flag (the next operand)."""


@pytest.fixture(scope="module")
def data() -> ModuleType:
    spec = importlib.util.spec_from_file_location("lufia2ow_data", DATA_FILE)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def restore() -> Iterator[None]:
    rom, patch = session(), selected()
    yield
    select(patch)
    use(rom)


def _scripts() -> Iterator[tuple[str, EventScript]]:
    reset_map_events()
    for index in range(MapEventObject.count):
        map_event = MapEvent.from_index(index)
        map_event.read()
        for event_list in map_event.event_lists:
            for script in event_list.events:
                yield _signature(index, script), script


def _removed_items(script: EventScript) -> set[int]:
    items = set()
    for ins in script.instructions:
        if ins.opcode in REMOVE_ITEM:
            item = ins.operands[0]
            assert isinstance(item, int)
            items.add(REMOVE_ITEM[ins.opcode] + item)
    return items


def _chain_flags(operands: list[Operand]) -> Iterator[int]:
    """The flags a ``0x14`` condition chain tests (its operands walked as ``compiler._emit_variable`` emits them)."""
    queue = list(operands)
    while queue:
        code = queue.pop(0)
        assert isinstance(code, int)
        if code == 0xFF:  # noqa: PLR2004
            return
        if code & 0xF0 in (0xF0, 0x10, 0xC0):
            del queue[:2]
        elif code & 0xE0 == 0x20:  # noqa: PLR2004
            del queue[:1]
        else:
            flag = queue.pop(0)
            if code in CHAIN_FLAG_CODES:
                assert isinstance(flag, int)
                yield flag


def _tested_flags(script: EventScript) -> set[int]:
    flags: set[int] = set()
    for ins in script.instructions:
        if ins.opcode in FLAG_BRANCHES:
            flag = ins.operands[0]
            assert isinstance(flag, int)
            flags.add(flag)
        elif ins.opcode == CONDITION:
            flags.update(_chain_flags(ins.operands))
    return flags


def _hand_in(hand_in: HandIn) -> EventScript:
    signature = f"{hand_in.map_index:02X}-B-{hand_in.script_index:02X}"
    return next(script for sig, script in _scripts() if sig == signature)


def _at(script: EventScript, offset: int) -> Instruction:
    return next(ins for ins in script.instructions if ins.line == offset)


@pytest.mark.usefixtures("restore")
def test_no_scenario_hand_in_tests_its_grants_flag(data: ModuleType) -> None:
    build(vanilla_image(files.original_file), OPTIONS)
    flags_by_item: dict[int, set[int]] = {}
    for _, _, _, item, _, flags in data.GRANTS:
        if item in data.SCENARIO_ITEMS:
            flags_by_item.setdefault(item, set()).update(flags)
    gated = [
        (signature, item, sorted(_tested_flags(script) & flags_by_item[item]))
        for signature, script in _scripts()
        for item in _removed_items(script) & flags_by_item.keys()
        if _tested_flags(script) & flags_by_item[item]
    ]
    assert not gated, "these scripts take a scenario item, gated on its grant's flag"


@pytest.mark.usefixtures("restore")
def test_hand_ins_jump_to_the_same_reward_and_still_take_the_item() -> None:
    image = vanilla_image(files.original_file)
    select(Patch.VANILLA)
    open_rom(image)
    vanilla = {}
    for hand_in in HAND_INS:
        script = _hand_in(hand_in)
        gate = next(ins for ins in script.instructions if ins.opcode == FLAG_BRANCHES[0] and ins.operands[0] == hand_in.flag)
        target = gate.operands[1]
        assert isinstance(target, Address)
        vanilla[hand_in] = (gate.line, _at(script, target.offset))

    build(image, OPTIONS)
    for hand_in in HAND_INS:
        script = _hand_in(hand_in)
        line, reward = vanilla[hand_in]
        gate = _at(script, line)
        assert gate.opcode == CONDITION
        assert gate.operands[:4] == [0xC2, hand_in.item, 1, 0x20]
        assert gate.operands[5:] == [0xFF]
        target = gate.operands[4]
        assert isinstance(target, Address)
        moved = _at(script, target.offset)
        assert (moved.opcode, moved.operands) == (reward.opcode, reward.operands)
        assert hand_in.item in _removed_items(script)
        assert hand_in.flag not in _tested_flags(script)


@pytest.mark.usefixtures("restore")
def test_open_world_doesnt_gate_hand_ins(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[None] = []
    monkeypatch.setattr(build_module, "gate_hand_ins_on_items", lambda: calls.append(None))
    build(vanilla_image(files.original_file), OPEN_WORLD_OPTIONS)
    assert not calls


def _set_flags(script: EventScript) -> set[int]:
    flags = set()
    for ins in script.instructions:
        if ins.opcode == SET_FLAG:
            flag = ins.operands[0]
            assert isinstance(flag, int)
            flags.add(flag)
    return flags


def _engine_gates(script: EventScript) -> list[Instruction]:
    """The script's ``14(C2-Engine-01-20-@target-FF)`` gates."""
    return [
        ins for ins in script.instructions
        if ins.opcode == CONDITION and ins.operands[:4] == [0xC2, ENGINE, 1, 0x20] and ins.operands[5:] == [0xFF]
    ]


def _target(script: EventScript, gate: Instruction) -> Instruction:
    target = gate.operands[1] if gate.opcode in FLAG_BRANCHES else gate.operands[4]
    assert isinstance(target, Address)
    return _at(script, target.offset)


@pytest.mark.usefixtures("restore")
def test_no_engine_removal_is_reached_only_through_the_grant_scenes_flag() -> None:
    """The Engine can come from another world: no script that takes it may need a flag only the Gratze chain sets."""
    build(vanilla_image(files.original_file), OPTIONS)
    scripts = dict(_scripts())
    chain_flags = set().union(*(_set_flags(scripts[signature]) for signature in ENGINE_GRANT_CHAIN))
    elsewhere = set().union(*(_set_flags(script) for sig, script in scripts.items() if sig not in ENGINE_GRANT_CHAIN))
    only_chain = chain_flags - elsewhere
    assert EventFlag.GOT_ENGINE in only_chain
    removers = [(sig, script) for sig, script in scripts.items() if ENGINE in _removed_items(script)]
    assert [sig for sig, _ in removers] == [LEXIS_LAB]
    for signature, script in removers:
        item_targets = [_target(script, gate) for gate in _engine_gates(script)]
        for gate in script.instructions:
            if gate.opcode == FLAG_BRANCHES[0] and gate.operands[0] in only_chain:
                assert _target(script, gate) in item_targets, f"{signature} {gate} has no Engine gate beside it"


@pytest.mark.usefixtures("restore")
def test_lexis_lab_builds_the_airship_from_a_held_engine() -> None:
    """The Engine gate sits between the GOT_AIRSHIP and GOT_ENGINE gates, and jumps where GOT_ENGINE does."""
    build(vanilla_image(files.original_file), OPTIONS)
    script = dict(_scripts())[LEXIS_LAB]
    ladder = [
        ins.operands[0] if ins.opcode == FLAG_BRANCHES[0] else "Engine"
        for ins in script.instructions
        if ins.opcode == FLAG_BRANCHES[0] or ins in _engine_gates(script)
    ]
    airship = ladder.index(EventFlag.GOT_AIRSHIP)
    assert ladder[airship + 1 : airship + 3] == ["Engine", EventFlag.GOT_ENGINE]
    (engine_gate,) = _engine_gates(script)
    flag_gate = next(
        ins for ins in script.instructions if ins.opcode == FLAG_BRANCHES[0] and ins.operands[0] == EventFlag.GOT_ENGINE
    )
    branch = _target(script, engine_gate)
    assert branch is _target(script, flag_gate)
    assert (branch.opcode, branch.operands) == (0x33, [0x15, 0x00])
    tail = script.instructions[script.instructions.index(branch) :]
    take = next(ins for ins in tail if ins.opcode in REMOVE_ITEM)
    assert REMOVE_ITEM[take.opcode] + take.operands[0] == ENGINE
    after = tail[tail.index(take) + 1 :]
    assert (after[0].opcode, after[0].operands) == (SET_FLAG, [EventFlag.GOT_AIRSHIP])


@pytest.mark.usefixtures("restore")
def test_open_world_doesnt_gate_the_lab(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[None] = []
    monkeypatch.setattr(build_module, "gate_airship_on_engine", lambda: calls.append(None))
    build(vanilla_image(files.original_file), OPEN_WORLD_OPTIONS)
    assert not calls


CROWN_LINE = "10-C-03"
CROWN_HAND_IN = "10-B-59"


@pytest.mark.usefixtures("restore")
def test_crown_line_stops_after_the_hand_in() -> None:
    """Alunze's Crown line starts with the hand-in's own RETURNED_CROWN_ALUNZE gate, jumping to its end (Iris-Dev#26)."""
    build(vanilla_image(files.original_file), OPTIONS)
    scripts = dict(_scripts())
    line, hand_in = scripts[CROWN_LINE], scripts[CROWN_HAND_IN]
    gate = line.instructions[0]
    assert (gate.opcode, gate.operands[0]) == (FLAG_BRANCHES[0], EventFlag.RETURNED_CROWN_ALUNZE)
    assert (hand_in.instructions[0].opcode, hand_in.instructions[0].operands[0]) == (gate.opcode, gate.operands[0])
    assert _target(line, gate) is line.instructions[-1]
    assert (line.instructions[-1].opcode, line.instructions[-1].operands) == (0x00, [])
    crown = line.instructions[1]
    assert (crown.opcode, crown.operands[:2]) == (CONDITION, [0xC2, 459])
    assert _target(line, crown) is line.instructions[-1]


@pytest.mark.usefixtures("restore")
def test_open_world_empties_the_crown_line() -> None:
    build(vanilla_image(files.original_file), OPEN_WORLD_OPTIONS)
    assert [ins.opcode for ins in dict(_scripts())[CROWN_LINE].instructions] == [0x00]
