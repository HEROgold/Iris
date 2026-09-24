"""everyone_learns_reset: Reset is learnable by every character, and the tutorial teaches it to the whole party."""

from collections.abc import Iterator

import pytest

from helpers.files import write_file
from patches.HEROgold.everyone_learns_reset import ALL_CHARACTERS, RESET, TUTORIAL_MAP, everyone_learns_reset
from scripting.l2basm.records import spell_records
from structures.character import PlayableCharacter
from structures.event_script.containers import MapEvent
from tests.reset_file import reset_file


SPELL_CHARACTERS = 10  # record offset of the "who can learn this spell" byte


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    reset_file()
    MapEvent._cache.clear()  # noqa: SLF001
    yield
    reset_file()
    MapEvent._cache.clear()  # noqa: SLF001


def _output(start: int, size: int) -> bytes:
    write_file.flush()
    write_file.seek(start)
    return write_file.read(size)


def test_reset_is_learnable_by_everyone() -> None:
    everyone_learns_reset()
    record = spell_records(write_file)[RESET]
    assert _output(record.start + SPELL_CHARACTERS, 1) == bytes([ALL_CHARACTERS])


def test_both_tutorial_grants_teach_maxim_and_every_party_member() -> None:
    everyone_learns_reset()
    map_event = MapEvent.from_index(TUTORIAL_MAP)
    grants = [
        script for event_list in map_event.event_lists for script in event_list.events
        if any(i.opcode == 0x23 and i.operands == [0, RESET] for i in script.instructions)  # noqa: PLR2004
    ]
    assert len(grants) == 2  # noqa: PLR2004 (the Reset lesson's two variants)
    for script in grants:
        data = _output(script.pointer, len(script.raw))
        assert data == bytes(script.raw)
        assert bytes([0x23, 0, RESET]) in data
        for index in range(1, 7):
            flag = PlayableCharacter.from_index(index).party_flag
            teach = bytes([0x23, index, RESET])
            at = data.index(teach)
            assert data[at - 4] == 0x6A  # noqa: PLR2004 (6A flag lo hi: skip the grant when not in the party)
            assert data[at - 3] == flag
