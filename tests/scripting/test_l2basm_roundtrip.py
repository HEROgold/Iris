"""Every vanilla and base-patch L2BASM record parses and reassembles to its exact bytes."""

from collections.abc import Iterator

import pytest

from enums.patches import Patch
from helpers.files import read_file, write_file
from patcher import apply_patch
from scripting.core import Label, assemble
from scripting.l2basm import parse_record
from scripting.l2basm.records import ALL_READERS, RecordSource, read_record
from tests.reset_file import reset_file


EXPECTED_SCRIPTS = {"monster": 391, "capsule": 70, "item": 202, "spell": 40, "ip_effect": 141, "subroutine": 41}


@pytest.fixture(autouse=True)
def _clean_output() -> Iterator[None]:
    reset_file()
    yield
    reset_file()


def _round_trip(source: object, rec: RecordSource) -> None:
    if not rec.entries:  # every entry points outside the record (shared code in some base patches)
        return
    record = read_record(source, rec)  # type: ignore[arg-type]
    parsed = parse_record(record, rec.entries, start=rec.script_start)
    assert assemble(parsed.script, parsed.start).data == record[parsed.start : parsed.end], (rec.table, rec.index)
    names = {item.name for item in parsed.script.body if isinstance(item, Label)}
    assert set(rec.entries) <= names


@pytest.mark.parametrize("table", sorted(ALL_READERS))
def test_every_vanilla_record_round_trips(table: str) -> None:
    records = ALL_READERS[table](read_file)
    assert sum(len(rec.entries) for rec in records) == EXPECTED_SCRIPTS[table]
    assert not any(rec.external for rec in records)
    for rec in records:
        _round_trip(read_file, rec)


@pytest.mark.parametrize("base", [Patch.FRUE, Patch.SPEKKIO, Patch.KUREJI])
@pytest.mark.parametrize("table", sorted(ALL_READERS))
def test_every_base_patch_record_round_trips(base: Patch, table: str) -> None:
    apply_patch(base)
    write_file.flush()
    for rec in ALL_READERS[table](write_file):
        _round_trip(write_file, rec)


def test_ten_monsters_share_blocks_between_attack_and_defense() -> None:
    shared = 0
    for rec in ALL_READERS["monster"](read_file):
        if len(rec.entries) == 2:  # noqa: PLR2004
            parsed = parse_record(read_record(read_file, rec), rec.entries, start=rec.script_start)
            shared += _reach_overlaps(parsed)
    assert shared == 10  # noqa: PLR2004


def _reach_overlaps(parsed: object) -> int:
    from scripting.l2basm.edit import reachable  # noqa: PLC0415 (edit.py arrives in Task 7)

    script = parsed.script  # type: ignore[attr-defined]
    return int(bool(reachable(script, "attack") & reachable(script, "defense")))


def test_ip_effects_24_to_26_resolve_against_the_marker() -> None:
    records = ALL_READERS["ip_effect"](read_file)
    for index in (24, 25, 26):
        rec = records[index]
        parsed = parse_record(read_record(read_file, rec), rec.entries, start=rec.script_start)
        assert "L_001E" in {item.name for item in parsed.script.body if isinstance(item, Label)}


def test_foomy_m_learnable_block_is_parsed() -> None:
    rec = ALL_READERS["capsule"](read_file)[1]
    parsed = parse_record(read_record(read_file, rec), rec.entries, start=rec.script_start)
    assert "L_0069" in {item.name for item in parsed.script.body if isinstance(item, Label)}
