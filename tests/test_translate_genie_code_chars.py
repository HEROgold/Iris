from patcher import translate_game_genie_code_snes


def test_translate_genie_code_chars():
    code = "ABCD-EFFF"
    code = code.replace("-", "")
    address, data = translate_game_genie_code_snes(code)

    assert address == 0xC4A704, f"Expected 0xC4A704, got {address:x}"
    assert data == 0xC9, f"Expected 0xC9, got {data:x}"