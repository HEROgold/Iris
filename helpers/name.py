from bitstring import BitArray

from helpers.addresses import address_from_lorom
from helpers.files import read_file, restore_pointer, write_file


END = b"\x00"
COMPRESS = b"\x0A"
COMPRESSED_NAME_OFFSET = 0x878000
COMPRESSED_NAME_END = 0x878FFF
COMPRESSED_NAMES_START = address_from_lorom(COMPRESSED_NAME_OFFSET)
COMPRESSED_NAMES_END = address_from_lorom(COMPRESSED_NAME_END)

# Compression constants
MIN_COMPRESSION_LENGTH = 3
MAX_COMPRESSION_LENGTH = 17
MAX_ADDRESS_OFFSET = 0xFFF  # 12 bits maximum

def read_compressed_name(pointer: int) -> bytes:
    read_file.seek(pointer)
    name = b""
    while True:
        name += read_file.read(1)
        if name.endswith(b"\x00"):
            break
    return name


def read_as_decompressed_name(pointer: int) -> bytes:
    """Read a name from the ROM. Also decompresses the name from the ROM."""
    read_file.seek(pointer)
    name = read = read_file.read(1)
    while read != END:
        if read == COMPRESS:
            read_file.seek(read_file.tell() + 2)
            decompress_name(name)
        read = read_file.read(1)
        name += read
    return name

@restore_pointer
def decompress_name(name: bytes) -> None:
    # 12 lower bits = address,
    # 4 higher bits = bytes to copy -2
    # stored in byte1 and byte2
    byte1 = BitArray(read_file.read(1))
    byte2 = BitArray(read_file.read(1))
    length = byte2[:4].uint + 2 # Get first digit, add 2
    copy_address = address_from_lorom((byte2[4:] + byte1).uint + COMPRESSED_NAME_OFFSET)
    read_file.seek(copy_address)
    name += read_file.read(length) # + b"\x0A" # we add a mark, so we can split later.??

@restore_pointer
def find_substring_in_rom(target: bytes) -> int | None:
    """
    Find a substring in the ROM's compressed name area.

    Args:
        target: The bytes to search for

    Returns:
        The ROM address where the substring was found, or None if not found
    """
    # Search in the compressed name area
    read_file.seek(COMPRESSED_NAMES_START)
    search_data = read_file.read(COMPRESSED_NAMES_END - COMPRESSED_NAMES_START)

    # Find the target in the search data
    pos = search_data.find(target)
    if pos != -1:
        return COMPRESSED_NAMES_START + pos

    return None

def create_compression_reference(address: int, copy_size: int) -> bytes:
    """
    Create the 2-byte operand of a ``0x0A`` back-reference.

    The game reads it as a little-endian word: the low 12 bits are the source's offset from ``$87:8000``
    (file ``0x38000``), the high 4 bits are ``copy_size - 2`` (terrorwave ``parse_name``).

    Args:
        address: File offset to copy from, inside the compressed-name window
        copy_size: Number of bytes to copy from address (3-17)
    """
    offset = address - COMPRESSED_NAMES_START
    if not 0 <= offset <= MAX_ADDRESS_OFFSET:
        msg = f"back-reference source {address:#x} is outside the name window"
        raise ValueError(msg)
    return (((copy_size - 2) & 0xF) << 12 | offset).to_bytes(2, "little")


def compress_name(pointer: int, name: bytes) -> bytes:
    """
    The bytes that encode ``name`` at ``pointer``, ending with the ``0x00`` terminator. Writes nothing.

    ``pointer`` matters: a run of the name is replaced by a back-reference only when the same bytes already sit in
    the name window before ``pointer``, so the same name encodes differently at different addresses.

    Args:
        pointer: ROM address the compressed name will be written to
        name: The name to compress, without terminator
    """
    # O(n^2)
    # First tries to find end to front matches
    # If no substring is found, it shortens the front, and finds end to front again.
    # Continues until all bytes are written.
    # Each word iteration: world, worl, wor, wo, w.
    # then
    # World > orld > rld > ld
    # etc.
    out = bytearray()
    written_bytes = 0
    while written_bytes < len(name):
        # Try to find the longest substring that exists elsewhere in ROM. Also store it's size.
        best_match = None
        size = 0

        # Check substrings from longest to shortest (minimum 2 bytes)
        for length in range(min(MAX_COMPRESSION_LENGTH, len(name) - written_bytes), MIN_COMPRESSION_LENGTH, -1):
            substring = name[written_bytes:written_bytes+length]
            target_address = find_substring_in_rom(substring)

            if target_address is not None:
                # Only reference bytes before the name: the old name is still at pointer while this runs.
                if target_address + length > pointer:
                    continue

                best_match = target_address
                size = length
                break

        if best_match and size > MIN_COMPRESSION_LENGTH:
            out += COMPRESS + create_compression_reference(best_match, size)
            written_bytes += size
        else:
            out += name[written_bytes:written_bytes+1]
            written_bytes += 1

    return bytes(out + END)


def write_compressed_name(pointer: int, name: bytes) -> None:
    """
    Write a name to ROM with compression, terminator included (see :func:`compress_name`).

    Args:
        pointer: ROM address where to write the compressed name
        name: The name string to compress and write
    """
    write_file.seek(pointer)
    write_file.write(compress_name(pointer, name))
