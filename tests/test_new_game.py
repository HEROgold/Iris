"""The new-game hook at $03:ADC2: unlocked Warp destinations, and ``--skip-tutorial``'s flags and Reset for Maxim."""

from collections.abc import Iterator

import pytest

from helpers.addresses import address_from_lorom
from helpers.files import write_file
from patches.HEROgold.new_game import EVENT_FLAGS, TUTORIAL_FLAGS, apply_new_game_hook
from tests.reset_file import reset_file


HANDOFF = 0x1ADC2  # $03:ADC2  LDA #$FF : STA $099D : JMP $B18E  (8 bytes)
JML = 0x5C


@pytest.fixture(autouse=True)
def _clean_output() -> Iterator[None]:
    reset_file()
    yield
    reset_file()


def _hook() -> bytes:
    write_file.flush()
    write_file.seek(0)
    out = write_file.read()
    assert out[HANDOFF] == JML
    assert out[HANDOFF + 4 : HANDOFF + 8] == b"\xea" * 4
    start = address_from_lorom(int.from_bytes(out[HANDOFF + 1 : HANDOFF + 4], "little"))
    return out[start : start + 0x100]


def _sets_flag(hook: bytes, flag: int) -> bool:
    """``LDA.l $7E:byte : ORA #mask : STA.l $7E:byte`` for event flag ``flag`` (bit n%8 of $7E:077E + n/8)."""
    byte = (EVENT_FLAGS + flag // 8).to_bytes(2, "little")
    return bytes([0xAF, *byte, 0x7E, 0x09, 1 << flag % 8, 0x8F, *byte, 0x7E]) in hook


def _rejoins_vanilla(hook: bytes) -> bool:
    """``STA.l $7E099D : JML $03B18E`` with A = $FF: loaded right before, or left over from the Warp stores."""
    at = hook.find(bytes.fromhex("8F 9D 09 7E 5C 8E B1 03"))
    return at >= 2 and (hook[at - 2 : at] == bytes.fromhex("A9 FF") or hook[at - 4 : at] == bytes.fromhex("8F 96 09 7E"))


def test_warps_only_keeps_the_vanilla_handoff_and_sets_no_tutorial_flag() -> None:
    apply_new_game_hook(unlock_warps=True, skip_tutorial=False)
    hook = _hook()
    assert bytes.fromhex("8F 7B 09 7E") in hook  # first Warp destination byte
    assert _rejoins_vanilla(hook)
    assert not any(_sets_flag(hook, flag) for flag in TUTORIAL_FLAGS)
    assert bytes.fromhex("22 3D FD 82") not in hook


def test_skip_tutorial_sets_every_tutorial_flag() -> None:
    apply_new_game_hook(unlock_warps=True, skip_tutorial=True)
    hook = _hook()
    for flag in TUTORIAL_FLAGS:
        assert _sets_flag(hook, flag), hex(flag)
    assert _rejoins_vanilla(hook)


def test_skip_tutorial_teaches_maxim_reset_with_the_games_own_routine() -> None:
    apply_new_game_hook(unlock_warps=False, skip_tutorial=True)
    hook = _hook()
    # as event opcode 23 does: spell in $0A0B, character in A, JSL $82:FD3D; with DBR set to a WRAM-mirroring bank
    at = hook.index(bytes.fromhex("22 3D FD 82"))
    assert hook[at - 7 : at] == bytes.fromhex("A9 26 8D 0B 0A A9 00")
    assert bytes.fromhex("A9 80 48 AB") in hook[:at]  # LDA #$80 : PHA : PLB
    assert bytes.fromhex("8F 7B 09 7E") not in hook


def test_tutorial_flags_match_the_cave_events() -> None:
    # 0x15 finished tutorial, 0x77 Tia's cave scene seen, 0xAC Reset lesson done, then the cave's trigger-tile lessons.
    assert set(TUTORIAL_FLAGS) == {0x15, 0x77, 0xAC, 0x9E, 0x9F, 0xA0, 0xA1, 0xA2, 0xA3, 0xAB}
