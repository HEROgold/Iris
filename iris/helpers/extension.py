

import contextlib
import shutil
from pathlib import Path
from typing import Literal


type ValidExtensions = Literal[".sfc", ".smc"]
valid_extensions = ".sfc", ".smc"

def convert_rom(file_path: Path, extension: ValidExtensions) -> Path:
    if file_path.suffix not in valid_extensions or extension not in valid_extensions:
        msg = f"Invalid extension: {file_path.suffix}."
        raise ValueError(msg)
    new = file_path.with_suffix(extension)
    with contextlib.suppress(shutil.SameFileError):
        shutil.copy(file_path, new)
    if has_header(new):
        remove_header(new)
    return new


def has_header(file: Path) -> bool:
    """Check if a file has a header."""
    size = file.stat().st_size
    if size % 0x400 == 0:
        return False
    if size % 0x200 == 0:
        return True
    msg = "Inappropriate file size for SNES rom file."
    raise Exception(msg)


def remove_header(rom: Path) -> None:
    """Remove the header from a ROM file. If the file does not have a header, nothing happens."""
    with rom.open("r+b") as rf:
        data = rf.read()
        rf.seek(0)
        rf.write(data[0x200:])
