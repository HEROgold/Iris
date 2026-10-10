"""--debug-party: maxed starting characters and Elcid toggles that skip the found check."""

from collections.abc import Iterator

import pytest

from helpers.bits import read_little_int
from helpers.files import write_file
from patches.HEROgold.debug_party import MAX_LEVEL, MAX_STAT, max_out_party
from patches.HEROgold.party_toggle import _NOT_IN_PARTY, _toggle  # pyright: ignore[reportPrivateUsage]
from structures.character import PlayableCharacter
from tables import CharacterObject, CharLevelObject
from tests.reset_file import reset_file


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    reset_file()
    yield
    reset_file()


def test_every_character_starts_maxed() -> None:
    max_out_party()
    write_file.flush()
    for index in range(7):
        write_file.seek(CharLevelObject.pointers[index])
        assert read_little_int(write_file, CharLevelObject.level) == MAX_LEVEL
        write_file.seek(CharacterObject.address + index * CharacterObject.size)
        assert [read_little_int(write_file, 2) for _ in range(7)] == [MAX_STAT] * 7


def test_toggle_without_found_check_sets_found_and_joins() -> None:
    character = PlayableCharacter.from_index(3)
    normal = {i.line: i for i in _toggle(character)}
    debug = {i.line: i for i in _toggle(character, require_found=False)}
    assert normal[_NOT_IN_PARTY].opcode == 0x6A  # noqa: PLR2004
    assert debug[_NOT_IN_PARTY].opcode == 0x1A  # noqa: PLR2004
    assert debug[_NOT_IN_PARTY].operands == [character.found_flag]
