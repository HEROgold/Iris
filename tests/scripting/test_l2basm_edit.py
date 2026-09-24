"""reachable and replace_entry: editing one entry keeps blocks another entry uses."""

import pytest

from errors import ScriptAssemblyError
from scripting.core import Label, assemble
from scripting.l2basm import parse_record
from scripting.l2basm.edit import reachable, replace_entry
from scripting.l2basm.helpers import end, flee, label, physical_attack, sequence


SHARED = bytes.fromhex("03 06 00 03 09 00 28 00 00 29 00")
# attack: goto +6 ; defense: goto +9 ; +6: 28 00 (attack only) ... defense block at +9: 29 00


def test_reachable_follows_jumps() -> None:
    script = parse_record(SHARED, {"attack": 0, "defense": 3}).script
    attack = reachable(script, "attack")
    defense = reachable(script, "defense")
    assert attack.isdisjoint(defense)


def test_replace_entry_keeps_the_other_entry_intact() -> None:
    parsed = parse_record(bytes.fromhex("03 06 00 03 06 00 28 00"), {"attack": 0, "defense": 3})
    replace_entry(parsed.script, "attack", sequence(flee(), end()))
    out = assemble(parsed.script, parsed.start)
    assert out.data[out.labels["defense"] :][:3] == bytes([0x03, *(out.labels["L_0006"]).to_bytes(2, "little")])
    assert out.data[out.labels["attack"] : out.labels["attack"] + 2] == b"\x2a\x00"
    assert out.data[out.labels["L_0006"] : out.labels["L_0006"] + 2] == b"\x28\x00"


def test_replace_entry_drops_blocks_only_that_entry_used() -> None:
    parsed = parse_record(SHARED, {"attack": 0, "defense": 3})
    replace_entry(parsed.script, "attack", sequence(flee(), end()))
    out = assemble(parsed.script, parsed.start).data
    assert b"\x28\x00" not in out


def test_reusing_an_existing_label_name_raises() -> None:
    parsed = parse_record(SHARED, {"attack": 0, "defense": 3})
    replace_entry(parsed.script, "attack", sequence(label("defense"), physical_attack(), end()))
    with pytest.raises(ScriptAssemblyError, match="Duplicate label: 'defense'"):
        assemble(parsed.script, parsed.start)


def test_unknown_entry_raises() -> None:
    parsed = parse_record(SHARED, {"attack": 0, "defense": 3})
    with pytest.raises(KeyError, match="reaction"):
        replace_entry(parsed.script, "reaction", sequence(end()))
