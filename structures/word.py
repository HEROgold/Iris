from helpers.files import read_file, restore_pointer, write_file
from typing import Self
from helpers.bits import find_table_pointer
from abc_.pointers import TablePointer
from tables import WordObject


class Word(TablePointer):
    def __init__(self, word: str) -> None:
        self.word = word

    def __repr__(self) -> str:
        return f"Word: {self.word}"

    @classmethod
    def from_index(cls, index: int) -> Self:
        return cls.from_table(WordObject.address, index)

    @classmethod
    @restore_pointer
    def from_table(cls, address: int, index: int) -> Self:
        pointer = find_table_pointer(address, index)
        read_file.seek(pointer)

        reset_bit = b"\x00"

        word = bytes()
        while True:
            partial_data = read_file.read(1)
            if partial_data == reset_bit:
                break
            word += partial_data
        inst = cls(word.decode("utf-8"))
        super().__init__(inst, address, index)
        return inst

    def write(self):
        write_file.seek(self.pointer)
        write_file.write(self.word.encode("utf-8"))
        write_file.write(b"\x00")
