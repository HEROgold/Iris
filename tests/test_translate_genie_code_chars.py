import pytest

from helpers.files import write_file
from patcher import apply_game_genie_codes, translate_game_genie_code_snes
from tests.reset_file import reset_file
from tests.reset_file import test_equal as files_equal


def test_translate_genie_code_chars() -> None:
    code = "ABCD-EFFF"
    code = code.replace("-", "")
    address, data = translate_game_genie_code_snes(code)

    assert address == 0xC4A704, f"Expected 0xC4A704, got {address:x}"
    assert data == 0xC9, f"Expected 0xC9, got {data:x}"


def test_ram_codes_are_rejected_instead_of_written_to_rom() -> None:
    # "7E097BFF" is a Pro Action Replay code (RAM $7E:097B = FF). Decoded as a Game Genie code it points
    # at ROM 0x324454 and would write 0x3F there.
    with pytest.raises(ValueError, match="RAM"):
        apply_game_genie_codes("7E097BFF")
    files_equal()


def test_game_genie_codes_still_apply() -> None:
    try:
        apply_game_genie_codes("6DA0-C7AB")  # capsule always loves food: ROM 0x1464F = 0x80
        write_file.flush()
        write_file.seek(0x1464F)
        assert write_file.read(1) == b"\x80"
    finally:
        reset_file()
