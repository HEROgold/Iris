"""Writing capsule attack/reaction scripts: offsets, relocation, and no stale bytes.

Every test reads the per-seed output back (``write_file``) and walks the scripts with a small
branch-following decoder that lives here, independent of ``BattleScript.read``.
"""

from collections.abc import Iterator

import pytest

from enums.patches import Patch
from helpers.files import original_file, write_file
from patcher import apply_patch
from patches.HEROgold import foomy_s_firebird_valor
from structures.battle_builder import (
    Node,
    Target,
    end,
    flee,
    goto,
    label,
    on_chance,
    physical_attack,
    raw,
    resist,
    sequence,
)
from structures.battlescript import op_codes
from structures.capsule import CapsuleMonster
from structures.capsule_attack_names import capsule_attack_names
from tables import CapsuleObject
from tests.reset_file import reset_file


TABLE = CapsuleObject.address
BANK_END = 0xC0000  # capsule records and their script jumps stay inside LoROM bank $97
HEADER = 0x2B
REACTION_FIELD = 39
FOOMY_S = 0
SHOP_TABLE = 0xBEE9F  # u16 pointers relative to itself; Spekkio/Kureji add shops whose data sits in the free gap
SHOP_ENTRIES = 80  # more than any base uses (vanilla/FRUE 63, Spekkio 66); unused entries are 0x0000
_JUMPS = {0x03: 0, 0x04: 0, 0x05: 1, 0x06: 3, 0x07: 3, 0x08: 3, 0x09: 3, 0x0A: 3, 0x0B: 3, 0x3F: 1}


@pytest.fixture(autouse=True)
def _clean_output() -> Iterator[None]:
    capsule_attack_names.unload()
    reset_file()
    yield
    capsule_attack_names.unload()
    reset_file()


def _write(capsule: CapsuleMonster, attack: Node | None, reaction: Node | None) -> None:
    capsule.set_scripts(attack=attack, reaction=reaction)
    capsule.write()


def _output() -> bytes:
    write_file.flush()
    write_file.seek(0)
    return write_file.read()


def _record(rom: bytes, index: int) -> int:
    return TABLE + int.from_bytes(rom[TABLE + 2 * index:TABLE + 2 * index + 2], "little")


def _walk(rom: bytes, record: int, start: int) -> list[tuple[int, bytes]]:
    """Reachable instructions as (record-relative offset, bytes); asserts every opcode is known."""
    seen: set[int] = set()
    out = []
    stack = [start]
    while stack:
        pc = stack.pop()
        while pc not in seen:
            seen.add(pc)
            op = rom[record + pc]
            assert op in op_codes, f"unknown opcode {op:#x} at +{pc:#x}"
            ins = rom[record + pc:record + pc + 1 + op_codes[op]["params"]]
            out.append((pc, ins))
            if op in _JUMPS:
                k = 1 + _JUMPS[op]
                target = int.from_bytes(ins[k:k + 2], "little")
                if op == 0x03:
                    pc = target
                    continue
                stack.append(target)
            if op == 0x00:
                break
            pc += len(ins)
    return sorted(out)


def _footprint(rom: bytes, record: int) -> int:
    """One past the last reachable byte of either script, record-relative."""
    reaction = int.from_bytes(rom[record + REACTION_FIELD:record + REACTION_FIELD + 2], "little")
    ends = [off + len(ins) for off, ins in _walk(rom, record, HEADER) + _walk(rom, record, reaction)]
    return max(ends)


def _assert_packed(rom: bytes, record: int) -> None:
    """Attack at +0x2B, reaction right after its last reachable byte: no gaps, no stale bytes."""
    reaction = int.from_bytes(rom[record + REACTION_FIELD:record + REACTION_FIELD + 2], "little")
    attack = _walk(rom, record, HEADER)
    covered = sorted({b for off, ins in attack for b in range(off, off + len(ins))})
    assert covered == list(range(HEADER, reaction)), "attack script has unreachable bytes before the reaction"
    reach = _walk(rom, record, reaction)
    covered = sorted({b for off, ins in reach for b in range(off, off + len(ins))})
    assert covered == list(range(reaction, reaction + len(covered)))


def _short_attack() -> Node:
    return sequence(physical_attack(target=Target.ONE_FOE), end())


def _vanilla_reaction() -> Node:
    return sequence(resist(0x11), end())


def test_shorter_script_is_written_in_place_and_leftover_zeroed() -> None:
    before = _output()
    record = _record(before, FOOMY_S)
    old_end = record + _footprint(before, record)

    _write(CapsuleMonster.from_index(FOOMY_S), _short_attack(), _vanilla_reaction())

    after = _output()
    assert _record(after, FOOMY_S) == record
    assert after[record + HEADER:record + HEADER + 4] == bytes.fromhex("32 01 28 00")
    assert after[record + REACTION_FIELD:record + REACTION_FIELD + 2] == (HEADER + 4).to_bytes(2, "little")
    assert after[record + HEADER + 4:record + HEADER + 8] == bytes.fromhex("42 11 00 00")
    assert after[record + HEADER + 8:old_end] == bytes(old_end - record - HEADER - 8)
    assert after[:record] == before[:record]
    assert after[old_end:] == before[old_end:]
    _assert_packed(after, record)


def test_header_is_kept_apart_from_the_reaction_offset() -> None:
    before = _output()
    record = _record(before, FOOMY_S)
    _write(CapsuleMonster.from_index(FOOMY_S), _short_attack(), _vanilla_reaction())
    after = _output()
    assert after[record:record + REACTION_FIELD] == before[record:record + REACTION_FIELD]
    assert after[record + REACTION_FIELD + 2:record + HEADER] == before[record + REACTION_FIELD + 2:record + HEADER]


def _long_attack() -> Node:
    # 49 bytes: longer than Foomy S's 36-byte attack slot.
    return sequence(
        on_chance(0x40, "b"),
        raw(bytes([0x32, 0x01] * 20)),
        physical_attack(),
        end(),
        label("b"),
        flee(),
        end(),
    )


def test_growing_script_moves_the_record_into_free_space() -> None:
    before = _output()
    old = _record(before, FOOMY_S)
    old_end = old + _footprint(before, old)

    capsule = CapsuleMonster.from_index(FOOMY_S)
    _write(capsule, _long_attack(), _vanilla_reaction())

    after = _output()
    new = _record(after, FOOMY_S)
    assert new != old
    assert TABLE < new < BANK_END
    size = _footprint(after, new)
    assert new + size <= BANK_END
    assert before[new:new + size] == bytes(size), "relocated onto bytes that were not free"
    assert after[new:new + REACTION_FIELD] == before[old:old + REACTION_FIELD]
    assert after[old:old_end] == bytes(old_end - old), "old footprint must be zeroed"
    assert capsule.pointer == new
    _assert_packed(after, new)

    changed = {i for i in range(len(before)) if before[i] != after[i]}
    allowed = set(range(old, old_end)) | set(range(new, new + size)) | {TABLE, TABLE + 1}
    assert changed <= allowed


def test_relocation_skips_addresses_the_shop_table_points_at() -> None:
    capsule = CapsuleMonster.from_index(FOOMY_S)
    _write(capsule, _long_attack(), _vanilla_reaction())
    after = _output()
    new = _record(after, FOOMY_S)
    size = _footprint(after, new)
    shop_targets = {
        SHOP_TABLE + int.from_bytes(after[SHOP_TABLE + 2 * i:SHOP_TABLE + 2 * i + 2], "little")
        for i in range(SHOP_ENTRIES)
    }
    assert not any(new <= t < new + size for t in shop_targets)


def test_reaction_jumps_resolve_against_the_new_reaction_offset() -> None:
    reaction = sequence(goto("tail"), raw(bytes([0x42, 0x11, 0x00])), label("tail"), resist(0x11), end())
    _write(CapsuleMonster.from_index(FOOMY_S), _short_attack(), reaction)
    after = _output()
    record = _record(after, FOOMY_S)
    offset = HEADER + 4
    jump = int.from_bytes(after[record + offset + 1:record + offset + 3], "little")
    assert jump == offset + 6


def test_scripts_on_the_instance_match_the_output_after_writing() -> None:
    capsule = CapsuleMonster.from_index(FOOMY_S)
    _write(capsule, _long_attack(), _vanilla_reaction())
    after = _output()
    assert capsule.attack_script is not None
    assert capsule.reaction_script is not None
    assert capsule.attack_script.pointer == capsule.pointer + HEADER
    reaction = int.from_bytes(after[capsule.pointer + REACTION_FIELD:capsule.pointer + REACTION_FIELD + 2], "little")
    assert capsule.reaction_script.offset == reaction
    assert capsule.attack_script.bytecode == after[capsule.pointer + HEADER:capsule.pointer + reaction]


def test_capsule_write_after_relocation_targets_the_new_record() -> None:
    capsule = CapsuleMonster.from_index(FOOMY_S)
    _write(capsule, _long_attack(), _vanilla_reaction())
    moved = _output()
    capsule.write()
    assert _output() == moved


def test_unmodified_capsules_write_back_unchanged() -> None:
    before = _output()
    for index in range(CapsuleObject.count):
        CapsuleMonster.from_index(index).write()
    assert _output() == before


def test_attack_only_change_moves_the_kept_reaction() -> None:
    capsule = CapsuleMonster.from_index(FOOMY_S)
    _write(capsule, _short_attack(), None)
    after = _output()
    record = _record(after, FOOMY_S)
    assert after[record + REACTION_FIELD:record + REACTION_FIELD + 2] == (HEADER + 4).to_bytes(2, "little")
    assert after[record + HEADER + 4:record + HEADER + 8] == bytes.fromhex("42 11 00 00")
    _assert_packed(after, record)


def test_write_saves_the_attack_name_table_when_it_changed() -> None:
    names = capsule_attack_names
    index = names.add("Firebird")
    CapsuleMonster.from_index(FOOMY_S).write()
    assert not names.dirty
    capsule_attack_names.unload()
    assert capsule_attack_names[index] == "Firebird"


def test_write_leaves_the_attack_name_table_alone_when_unchanged() -> None:
    assert len(capsule_attack_names) > 0  # loaded, not changed
    before = _output()
    CapsuleMonster.from_index(FOOMY_S).write()
    assert _output()[0x12DF00:0x12E400] == before[0x12DF00:0x12E400]


@pytest.mark.parametrize("base", [Patch.FRUE, Patch.SPEKKIO, Patch.KUREJI])
def test_relocation_on_each_base_patch_only_uses_free_bytes(base: Patch) -> None:
    apply_patch(base)
    before = _output()
    _write(CapsuleMonster.from_index(FOOMY_S), _long_attack(), _vanilla_reaction())
    after = _output()
    new = _record(after, FOOMY_S)
    size = _footprint(after, new)
    assert before[new:new + size] == bytes(size)
    for index in range(CapsuleObject.count):
        record = _record(after, index)
        if index != FOOMY_S:
            assert after[record:record + 0x100] == before[record:record + 0x100]
        _footprint(after, record)  # every capsule's scripts still decode


def test_original_rom_is_untouched() -> None:
    _write(CapsuleMonster.from_index(FOOMY_S), _long_attack(), _vanilla_reaction())
    assert original_file.read_bytes()[_record(original_file.read_bytes(), FOOMY_S) + HEADER] == 0x0C


# -- the Foomy S Firebird/Valor patch --------------------------------------------------------------

FOOMY_ATTACK = bytes.fromhex(
    "0C 82 11 00 42 25 00 0A 80 81 80 5A 00"  # vanilla flee check: flee when HP lost % >= GUT threshold
    "05 30 4E 00 05 B0 44 00"                # ~19% Valor, else ~69% Firebird
    "32 01 28 00"                            # default: physical attack on one foe
    "32 01 47 78 00 54 05 01 4F 00"          # +0x44 Firebird on one foe, no MP
    "32 06 32 05 47 78 00 54 1E 01 4F 00"    # +0x4E Valor on all allies, no MP
    "2A 00",                                 # +0x5A flee
)


@pytest.mark.parametrize("base", [Patch.VANILLA, Patch.FRUE, Patch.SPEKKIO, Patch.KUREJI])
def test_foomy_patch_keeps_the_flee_check(base: Patch) -> None:
    apply_patch(base)
    before = _output()
    foomy_s_firebird_valor()
    after = _output()

    record = _record(after, FOOMY_S)
    reaction = HEADER + len(FOOMY_ATTACK)
    assert after[record + HEADER:record + reaction] == FOOMY_ATTACK
    assert after[record + REACTION_FIELD:record + REACTION_FIELD + 2] == reaction.to_bytes(2, "little")
    assert after[record + reaction:record + reaction + 4] == bytes.fromhex("42 11 00 00")
    _assert_packed(after, record)
    for index in range(1, CapsuleObject.count):
        other = _record(after, index)
        assert other == _record(before, index)
        assert after[other:other + _footprint(before, other)] == before[other:other + _footprint(before, other)]
