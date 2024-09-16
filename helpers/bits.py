from io import BufferedReader
from config import POINTER_SIZE
from helpers.files import read_file, write_file, restore_pointer

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
def find_table_pointer(address: int, index: int) -> int:
    """Find a pointer from a pointer table, doesn't change the current file."""
    read_file.seek(address + index * POINTER_SIZE)
    pointer = read_little_int(read_file, POINTER_SIZE)
    return address + pointer


def update_pointer_table(address: int, index: int, offset: int) -> None:
    """Set a pointer in a pointer table."""
    write_file.seek(address + index * POINTER_SIZE)
    write_file.write(offset.to_bytes(POINTER_SIZE, "little"))


def read_little_int(file: BufferedReader, size: int) -> int:
    return int.from_bytes(file.read(size), "little")


def bytes_overwrite(old: bytes, index: int, patch: bytes) -> bytes:
    size = len(patch)

    patched_code = old[:index] + patch + old[index+size:]
    return patched_code
