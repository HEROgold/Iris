"""everyone_learns_reset: Reset is learnable by every character; the tutorial cave stays vanilla (HER-232)."""

from collections.abc import Iterator

import pytest

from helpers.files import write_file
from patches.HEROgold.everyone_learns_reset import ALL_CHARACTERS, RESET, TUTORIAL_MAP, everyone_learns_reset
from scripting.l2basm.records import spell_records
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


def test_the_tutorial_cave_is_left_in_place() -> None:
    """HER-232: the grants don't fit map 5's container in place, and moving it breaks the cave in game."""
    from helpers.files import original_file  # noqa: PLC0415
    from tables import MapEventObject  # noqa: PLC0415

    everyone_learns_reset()
    record = MapEventObject.address + TUTORIAL_MAP * MapEventObject.size
    vanilla = original_file.read_bytes()
    assert _output(record, MapEventObject.size) == vanilla[record : record + MapEventObject.size]
    map_event = MapEvent.from_index(TUTORIAL_MAP)
    for event_list in map_event.event_lists:
        for script in event_list.events:
            assert _output(script.pointer, len(script.raw)) == vanilla[script.pointer : script.pointer + len(script.raw)]
