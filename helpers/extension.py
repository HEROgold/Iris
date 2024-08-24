

import shutil
from pathlib import Path
from typing import Literal


type ValidExtensions = Literal[".sfc", ".smc"]
valid_extensions = ".sfc", ".smc"

def convert_rom(file_path: Path, extension: ValidExtensions) -> Path:
    if file_path.suffix not in valid_extensions or extension not in valid_extensions:
        raise ValueError(f"Invalid extension: {file_path.suffix}.")
    new = file_path.with_suffix(extension)
    try:
        shutil.copy(file_path, new)
    except shutil.SameFileError:
        pass
    if has_header(new):
        remove_header(new)
    return new


def has_header(file: Path) -> bool:
    """Check if a file has a header."""
    size = file.stat().st_size
    if size % 0x400 == 0:
        return False
    elif size % 0x200 == 0:
        return True
    else:
        raise Exception("Inappropriate file size for SNES rom file.")


def remove_header(rom: Path):
    """Remove the header from a ROM file. If the file does not have a header, nothing happens."""
    with rom.open("r+b") as rf:
        data = rf.read()
        rf.seek(0)
        rf.write(data[0x200:])
