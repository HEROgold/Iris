from io import BufferedReader
from config import POINTER_SIZE
from helpers.files import read_file, restore_pointer

def read_nth_bit(byte: bytes, n: int) -> int:
    mask = 1 << n
    return (int.from_bytes(byte) & mask) >> n

def set_nth_bit(byte: bytes, n: int) -> bytes:
    # TODO: Verify if this is the correct way to set the nth bit
    mask = 1 << n
    return (int.from_bytes(byte) | mask).to_bytes(1, "little")

def get_true_bit_index(byte: bytes) -> int | None:
    for i in range(len(byte)):
        if read_nth_bit(byte, i) == 1:
            return i


@restore_pointer
def find_table_pointer(address: int, offset: int) -> int:
    """Find a pointer from a pointer table, doesn't change the file current."""
    read_file.seek(address + offset * POINTER_SIZE)
    pointer = read_little_int(read_file, POINTER_SIZE)
    return address + pointer


def read_little_int(file: BufferedReader, size: int) -> int:
    return int.from_bytes(file.read(size), "little")
