from helpers.files import original_file, write_file


def reset_file() -> None:
    """Restore the per-seed output to the original ROM, through the same handle every structure writes to."""
    write_file.seek(0)
    write_file.write(original_file.read_bytes())
    write_file.truncate()
    write_file.flush()


def test_equal() -> None:
    """Assert the output still equals the original ROM, then reset it so later tests start clean.

    Flushes ``write_file`` first (structure writes are buffered) and always compares whole files from
    offset 0.
    """
    write_file.flush()
    same = original_file.read_bytes() == _output_bytes()
    if not same:
        reset_file()
    assert same


def _output_bytes() -> bytes:
    write_file.seek(0)
    return write_file.read()
