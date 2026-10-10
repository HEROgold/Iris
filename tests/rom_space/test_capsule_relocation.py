"""Capsule records that grow move inside bank $97 (rom_space.Table), and only onto free bytes.

Moved from test_capsule_scripts.py; the decoder and helpers come from there.
"""

import pytest

from enums.patches import Patch
from patcher import apply_patch
from structures.capsule import CapsuleMonster
from tables import CapsuleObject
from tests.test_capsule_scripts import (  # noqa: F401 (_clean_output is the autouse fixture)
    BANK_END,
    FOOMY_S,
    REACTION_FIELD,
    SHOP_ENTRIES,
    SHOP_TABLE,
    TABLE,
    _assert_packed,
    _clean_output,
    _footprint,
    _long_attack,
    _output,
    _record,
    _vanilla_reaction,
    _write,
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


def test_capsule_write_after_relocation_targets_the_new_record() -> None:
    capsule = CapsuleMonster.from_index(FOOMY_S)
    _write(capsule, _long_attack(), _vanilla_reaction())
    moved = _output()
    capsule.write()
    assert _output() == moved


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
