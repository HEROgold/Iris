"""Contains files that are used for the project, also contains a file that is opened for fast reading.
Don't forget to close the file after importing from this module!
```python
from helpers.files import file
file.close()
```
"""

import shutil
from collections.abc import Callable
from pathlib import Path
from types import TracebackType
from typing import Any, Literal

from args import args

# Converts a ROM file to a different extension, and removes a header if present.
from helpers.extension import convert_rom


original_file = convert_rom(Path(args.file), ".smc")
read_file = original_file.open("rb")
"""Opened file, make sure you close this somewhere in the program!"""

new_file = original_file.with_stem(f"{original_file.stem}-{args.seed}").with_suffix(original_file.suffix)
write_file = new_file.open("wb+")
"""Opened file, make sure you close this somewhere in the program!"""
shutil.copy(original_file, new_file)



class BackupFile:
    def __init__(self, file: Path) -> None:
        self.file = file

    def __enter__(self) -> Path:
        self.original = self.file
        self.temp = self.original.with_suffix(".tmp")
        shutil.copy(self.original, self.temp)
        return self.temp

    def __exit__(
        self,
        exc_type: type | None,
        exc_value: Any | None,
        traceback: TracebackType | None,
    ) -> None | Literal[False]:
        if exc_type or exc_value or traceback:
            return False

        new = self.temp.with_stem(f"{self.temp.stem}").with_suffix(self.original.suffix)
        shutil.copy(self.temp, new)
        self.temp.unlink()
        return None


def restore_pointer[F, **P](func: Callable[P, F]) -> Callable[P, F]:
    """Restore the read_file pointer after the function is called."""
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> F:
        restore = read_file.tell()
        result = func(*args, **kwargs)
        read_file.seek(restore)
        return result
    return wrapper
