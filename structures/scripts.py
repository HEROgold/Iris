from helpers.files import write_file


class Subroutine:
    def __init__(self, name: str, pointer: int, *, size: int = 0) -> None:
        self.name = name
        self.pointer = pointer
        self._size = size

    @property
    def size(self):
        return self._size

    @property
    def bytecode(self):
        write_file.seek(self.pointer)
        return write_file.read(self.size)

    @property
    def end(self):
        return self.pointer + self.size
