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
from typing import IO, Any, Literal

from args import args
from logger import iris

# Converts a ROM file to a different extension, and removes a header if present.
from helpers.extension import convert_rom


# Below this many bytes a write is logged with its full hex; larger writes (asar's whole-ROM rewrite,
# sprite/tile blobs) log only their length so a single line never balloons to megabytes.
_HEX_LOG_LIMIT = 32


class LoggingFile:
    """Transparent proxy around the per-seed ROM handle that traces every mutation to ``iris.log``.

    Nearly every ROM write in Iris ultimately lands here as ``write_file.seek(addr); write_file.write(bytes)``
    (structure ``.write()`` methods, RealCritical raw writes, chest/event/zone writers, ``update_pointer_table``).
    Wrapping the handle once instruments all of them at ``.debug`` with zero per-callsite edits, naming the
    exact address and bytes changed. All other attributes/methods delegate to the real handle, so the proxy is
    behaviourally identical to the file object it wraps.
    """

    def __init__(self, file: IO[bytes]) -> None:
        self._file = file
        self._offset = file.tell()

    def __getattr__(self, name: str) -> Any:  # noqa: ANN401 - transparent delegation to the wrapped handle
        return getattr(self._file, name)

    def seek(self, offset: int, whence: int = 0) -> int:
        self._offset = self._file.seek(offset, whence)
        return self._offset

    def write(self, data: Any) -> int:  # noqa: ANN401 - accepts any bytes-like, like the real handle
        addr = self._offset
        detail = f", {bytes(data).hex()=}" if len(data) <= _HEX_LOG_LIMIT else ""
        iris.debug(f"write_file: {addr=:#08x} len={len(data)}{detail}")
        written = self._file.write(data)
        self._offset += written
        return written

    def truncate(self, size: int | None = None) -> int:
        iris.debug(f"write_file: truncate {size=}")
        return self._file.truncate(size)

    def flush(self) -> None:
        iris.debug("write_file: flush")
        self._file.flush()


original_file = convert_rom(Path(args.file), ".smc")
read_file = original_file.open("rb")
"""Opened file, make sure you close this somewhere in the program!"""

new_file = original_file.with_stem(f"{original_file.stem}-{args.seed}").with_suffix(original_file.suffix)
write_file = LoggingFile(new_file.open("wb+"))
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
