"""``start_capsule``: the new-game code gives a chosen capsule species, whatever the start map is."""

from collections.abc import Iterator

import pytest

from helpers.addresses import address_from_lorom
from helpers.files import write_file
from patches.HEROgold.start_capsule import start_capsule
from tests.reset_file import reset_file


CAPSULE_CHECK = 0x1AD80  # $83:AD80  LDA $0B51 : BIT #$02 : BEQ $ADAB  (7 bytes)
JML = 0x5C
JSL = 0x22


@pytest.fixture(autouse=True)
def _clean_output() -> Iterator[None]:
    reset_file()
    yield
    reset_file()


def _output() -> bytes:
    write_file.flush()
    write_file.seek(0)
    return write_file.read()


def _long(data: bytes, at: int) -> int:
    return address_from_lorom(int.from_bytes(data[at:at + 3], "little"))


def _hook(out: bytes) -> bytes:
    assert out[CAPSULE_CHECK] == JML
    assert out[CAPSULE_CHECK + 4:CAPSULE_CHECK + 7] == b"\xea\xea\xea"
    start = _long(out, CAPSULE_CHECK + 1)
    return out[start:start + 0x80]


def test_hook_replays_the_vanilla_check_and_rejoins_the_new_game_code() -> None:
    start_capsule(0)
    hook = _hook(_output())
    assert hook.startswith(bytes.fromhex("AD 51 0B 89 02"))  # LDA $0B51 : BIT #$02
    assert bytes.fromhex("5C 87 AD 83") in hook  # bit set: vanilla's own capsule branch
    assert bytes.fromhex("5C AB AD 83") in hook  # otherwise: the normal start (set_spawn_location's code)


def test_hook_builds_the_capsule_with_the_games_own_routines() -> None:
    start_capsule(2)
    hook = _hook(_output())
    assert bytes.fromhex("A9 07 8F 7F 0A 7E") in hook  # $0A7F = 7 before building member 7
    assert bytes.fromhex("22 15 C5 82 22 61 C2 82") in hook  # JSL $82:C515, JSL $82:C261
    # fake JSL into the join routine's tail: PHK, PEA return-1, LDA #species : PHA, JML $82:E7DB
    tail = hook.index(bytes.fromhex("5C DB E7 82"))
    assert hook[tail - 3:tail] == bytes.fromhex("A9 02 48")
    assert hook[tail - 7] == 0x4B  # PHK
    assert hook[tail - 6] == 0xF4  # PEA
    # RTL returns to the pushed address + 1: the instruction right after the JML, which rejoins $83:ADAB
    back = int.from_bytes(hook[tail - 5:tail - 3], "little") + 1
    hook_start = int.from_bytes(_output()[CAPSULE_CHECK + 1:CAPSULE_CHECK + 3], "little")
    assert back == hook_start + tail + 4
    assert hook[tail + 4:tail + 8] == bytes.fromhex("5C AB AD 83")


@pytest.mark.parametrize(("species", "name"), [(0, "Foomy"), (3, "Red F")])
def test_species_and_name_are_written(species: int, name: str) -> None:
    start_capsule(species, name)
    hook = _hook(_output())
    assert bytes([0xA9, species, 0x8F, 0xA3, 0x11, 0x7E]) in hook  # LDA #species : STA $7E11A3
    for i, char in enumerate(name.encode("ascii")):
        target = (0x7FF180 + species * 5 + i).to_bytes(3, "little")
        assert bytes([0xA9, char, 0x8F, *target]) in hook


def test_default_name_is_the_species_name() -> None:
    start_capsule(0)
    hook = _hook(_output())
    assert bytes([0xA9, ord("F"), 0x8F, *(0x7FF180).to_bytes(3, "little")]) in hook


@pytest.mark.parametrize(("species", "name"), [(7, None), (-1, None), (0, "Toolong"), (0, "")])
def test_rejects_bad_input(species: int, name: str | None) -> None:
    with pytest.raises(ValueError, match="capsule"):
        start_capsule(species, name)
