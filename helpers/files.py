"""The ROM session every structure reads and writes (HER-221).

``read_file`` and ``write_file`` are views of one in-memory image, the active :class:`api.Rom` session. Both see the
same bytes, so a structure can't read the original ROM behind an earlier patch's back. Nothing is written to disk
until :func:`save`.

The CLI opens the session explicitly (:func:`open_rom`). Anything else that touches ``read_file`` / ``write_file``
first opens a default session from ``--file``, so tests and scripts keep working unchanged. Importing this module
(or any structure) doesn't need ``--file``.

``original_file`` (the headerless source ROM on disk) and ``new_file`` (where :func:`save` writes by default) are
resolved on first use.
"""

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from api.rom import Rom, RomView
from args import args

# Converts a ROM file to a different extension, and removes a header if present.
from helpers.extension import convert_rom
from logger import iris


if TYPE_CHECKING:
    from enums.patches import Patch


_session: Rom | None = None


def _source() -> Path:
    if not args.file:
        msg = "No ROM session: pass --file, or open one with helpers.files.open_rom()."
        raise RuntimeError(msg)
    return convert_rom(Path(args.file), ".smc")


def output_path(source: Path | None = None) -> Path:
    """Where :func:`save` writes by default: the source ROM's name with the seed appended."""
    source = _source() if source is None else source
    return source.with_stem(f"{source.stem}-{args.seed}").with_suffix(source.suffix)


def use(rom: Rom | None) -> None:
    """Make ``rom`` the active session (``None`` drops it; the next use opens the default one again)."""
    global _session  # noqa: PLW0603
    _session = rom


def open_rom(path: Path | None = None, base: "Patch | None" = None) -> Rom:
    """Read ``path`` (default: ``--file``) into a new active session and apply the base patch to it."""
    rom = Rom.open(_source() if path is None else convert_rom(Path(path), ".smc"))
    use(rom)
    if base is not None:
        from patcher import apply_patch  # noqa: PLC0415 - patcher imports this module

        apply_patch(base)
    return rom


def session() -> Rom:
    """The active session, opening the default one (``--file``, no base patch) on first use."""
    if _session is None:
        iris.debug("Opening the default ROM session from --file.")
        return open_rom()
    return _session


def save(path: Path | None = None) -> Path:
    """Write the session's image to ``path`` (default: :func:`output_path`). The one disk write of a run."""
    rom = session()
    path = output_path(rom.source) if path is None else path
    rom.save(path)
    return path


def output_bytes() -> bytes:
    """A copy of the current image: what :func:`save` would write."""
    return bytes(session().image)


class _SessionFile:
    """``read_file`` / ``write_file``: forwards every call to the active session's read or write view."""

    def __init__(self, view: str) -> None:
        self._view = view

    def _target(self) -> RomView:
        return getattr(session(), self._view)

    def __getattr__(self, name: str) -> Any:  # noqa: ANN401 - transparent delegation, like a file object
        return getattr(self._target(), name)

    def __repr__(self) -> str:
        return f"<{self._view} view of the active ROM session>"

    # The hot paths, forwarded without __getattr__.
    def seek(self, offset: int, whence: int = 0) -> int:
        return self._target().seek(offset, whence)

    def tell(self) -> int:
        return self._target().tell()

    def read(self, size: int = -1, /) -> bytes:
        return self._target().read(size)

    def write(self, data: bytes | bytearray | memoryview) -> int:
        return self._target().write(data)


read_file = _SessionFile("reader")
"""The active session's image, read-only. Same bytes as ``write_file``."""
write_file = _SessionFile("writer")
"""The active session's image. Writes stay in memory until :func:`save`."""


def __getattr__(name: str) -> Path:
    """``original_file`` and ``new_file``, resolved from the session (or ``--file``) on first use."""
    if name == "original_file":
        return session().source or _source()
    if name == "new_file":
        return output_path(session().source)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def restore_pointer[F, **P](func: Callable[P, F]) -> Callable[P, F]:
    """Restore the read_file pointer after the function is called."""
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> F:
        restore = read_file.tell()
        result = func(*args, **kwargs)
        read_file.seek(restore)
        return result
    return wrapper
