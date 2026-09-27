"""``Rom``: one in-memory ROM image per run, read from disk once and written to disk once (HER-221).

Every structure reads and writes the same image through ``helpers.files.read_file`` / ``write_file``, which are
views of the active session. So a structure can't read the original ROM behind an earlier patch's back and undo it
(the HER-179 class of bugs), and nothing reaches the disk until :meth:`Rom.save`.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from logger import iris


if TYPE_CHECKING:
    from rom_space.pool import FreeSpace


HEADER_SIZE = 0x200
"""A copier header: ROM sizes are multiples of 0x400, so a file 0x200 past one has a header."""
_HEX_LOG_LIMIT = 32
"""Below this many bytes a write is logged with its full hex; larger writes (asar's whole-ROM result, sprite blobs)
log only their length."""


class RomView:
    """A file-like cursor over a :class:`Rom`'s image. Views share the image; each keeps its own position.

    Behaves like a ``BytesIO`` on the image: reading past the end returns fewer bytes, writing past the end grows the
    image (zero-filling any gap), and ``truncate`` shrinks it. ``flush`` and ``close`` do nothing: the image is only
    written to disk by :meth:`Rom.save`.
    """

    def __init__(self, rom: "Rom", *, writable: bool) -> None:
        self._rom = rom
        self._writable = writable
        self._position = 0

    def __repr__(self) -> str:
        return f"<RomView {'write' if self._writable else 'read'} at {self._position:#x}>"

    @property
    def closed(self) -> bool:
        return False

    def readable(self) -> bool:
        return True

    def writable(self) -> bool:
        return self._writable

    def seekable(self) -> bool:
        return True

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 1:
            offset += self._position
        elif whence == 2:  # noqa: PLR2004 - io.SEEK_END
            offset += len(self._rom.image)
        if offset < 0:
            msg = f"negative seek position {offset}"
            raise ValueError(msg)
        self._position = offset
        return offset

    def tell(self) -> int:
        return self._position

    def read(self, size: int = -1, /) -> bytes:
        image = self._rom.image
        end = len(image) if size is None or size < 0 else self._position + size
        data = bytes(image[self._position:end])
        self._position += len(data)
        return data

    def write(self, data: bytes | bytearray | memoryview) -> int:
        if not self._writable:
            msg = "read_file is read-only; write through write_file"
            raise OSError(msg)
        data = bytes(data)
        detail = f", {data.hex()=}" if len(data) <= _HEX_LOG_LIMIT else ""
        iris.debug(f"write_file: addr={self._position:#08x} len={len(data)}{detail}")
        image = self._rom.image
        if self._position > len(image):
            image.extend(bytes(self._position - len(image)))
        image[self._position:self._position + len(data)] = data
        self._position += len(data)
        return len(data)

    def truncate(self, size: int | None = None) -> int:
        size = self._position if size is None else size
        iris.debug(f"write_file: truncate {size=}")
        image = self._rom.image
        if size < len(image):
            del image[size:]
        return size

    def flush(self) -> None:
        """Nothing to do: every view writes straight into the shared image."""

    def close(self) -> None:
        """Nothing to do: the image lives until the session ends."""


class Rom:
    """One ROM image in memory, with a read view, a write view and the free-space pool over it."""

    def __init__(self, image: bytes, source: Path | None = None) -> None:
        self.image = bytearray(image)
        self.source = source
        self.reader = RomView(self, writable=False)
        self.writer = RomView(self, writable=True)
        self.pool: FreeSpace | None = None
        """Built by ``rom_space.pool()`` on first use, after base patches."""

    def __repr__(self) -> str:
        return f"<Rom {self.source} {len(self.image):#x} bytes>"

    @classmethod
    def open(cls, path: Path) -> "Rom":
        """Read ``path`` once, dropping a copier header. Nothing on disk changes."""
        data = path.read_bytes()
        if len(data) % 0x400 == HEADER_SIZE:
            data = data[HEADER_SIZE:]
        return cls(data, path)

    def save(self, path: Path) -> None:
        """Write the image to ``path``. The one disk write of a run."""
        path.write_bytes(self.image)
        iris.info(f"Wrote {path.name} ({len(self.image)} bytes).")
