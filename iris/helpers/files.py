"""The ROM session every structure reads and writes (HER-221).

``read_file`` and ``write_file`` are views of one in-memory image, the active :class:`api.Rom` session. Both see the
same bytes, so a structure can't read the original ROM behind an earlier patch's back. Nothing is written to disk
until :func:`save`.

Whoever runs Iris opens the session explicitly (:func:`open_rom`): the CLI, the tests' conftest, a headless build.
Importing this module (or any structure) doesn't need a ROM.

``original_file`` is the active session's source ROM on disk, resolved on first use.
"""

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from iris.api.rom import Rom, RomView

# Converts a ROM file to a different extension, and removes a header if present.
from iris.helpers.extension import convert_rom


if TYPE_CHECKING:
    from iris.enums.patches import Patch


_session: Rom | None = None
_resets: list[Callable[[], None]] = []


def output_path(source: Path, seed: int) -> Path:
    """The CLI's default output: the source ROM's name with the seed appended."""
    return source.with_stem(f"{source.stem}-{seed}").with_suffix(source.suffix)


def on_new_session[F: Callable[[], None]](reset: F) -> F:
    """Register ``reset`` to drop state read from the previous session whenever another one becomes active.

    Use it on every cache of ROM data (a decorator on the module's reset function), so two builds in one process
    can't see each other's ROM.
    """
    _resets.append(reset)
    return reset


def use(rom: Rom | None) -> None:
    """Make ``rom`` the active session (``None`` drops it), dropping every cache of the previous one."""
    global _session  # noqa: PLW0603
    _session = rom
    for reset in _resets:
        reset()


def open_rom(source: Path | bytes, base: "Patch | None" = None) -> Rom:
    """Read ``source`` (a ROM file, or its bytes) into a new active session and apply the base patch to it."""
    rom = Rom.open(convert_rom(source, ".smc")) if isinstance(source, Path) else Rom.from_bytes(source)
    use(rom)
    if base is not None:
        from iris.patcher import apply_patch  # noqa: PLC0415 - patcher imports this module

        apply_patch(base)
    return rom


def session() -> Rom:
    """The active session."""
    if _session is None:
        msg = "No ROM session: open one with helpers.files.open_rom()."
        raise RuntimeError(msg)
    return _session


def save(path: Path) -> Path:
    """Write the session's image to ``path``. The one disk write of a run."""
    session().save(path)
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
    """``original_file``: the active session's source ROM."""
    if name == "original_file":
        source = session().source
        if source is None:
            msg = "The active ROM session wasn't read from a file."
            raise RuntimeError(msg)
        return source
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
