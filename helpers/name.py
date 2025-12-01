from bitstring import BitArray

from helpers.addresses import address_from_lorom, address_to_lorom
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
    Create the 2-byte compression reference.

    Args:
        address: The address to copy from
        copy_size: Number of bytes to copy from address
    """
    return BitArray(uint=((address & 0xFFF) << 4) | ((copy_size - 2) & 0xF), length=16).tobytes()


def write_compressed_name(pointer: int, name: bytes) -> None:
    """
    Write a name to ROM with compression.

    Args:
        pointer: ROM address where to write the compressed name
        name: The name string to compress and write
    """
    # O(n^2)
    # First tries to find end to front matches
    # If no substring is found, it shortens the front, and finds end to front again.
    # Continues until all bytes are written.
    # Each word iteration: world, worl, wor, wo, w.
    # then
    # World > orld > rld > ld
    # etc.
    write_file.seek(pointer)

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
                # Avoid self-referencing.
                if target_address >= pointer + written_bytes:
                    continue

                best_match = target_address
                size = length
                break

        if best_match and size > MIN_COMPRESSION_LENGTH:
            # Write compression reference.
            write_file.write(COMPRESS)
            reference_bytes = create_compression_reference(best_match, size)
            write_file.write(reference_bytes)
            written_bytes += size
        else:
            # Write literal byte
            write_file.write(name[written_bytes:written_bytes+1])
            written_bytes += 1

    # Write null terminator
    # write_file.write(END)
    return None

def test_compression_round_trip(name: str, test_pointer: int = 0x100000) -> bool:
    """
    Test that compression and decompression work correctly for a given name.

    Args:
        name: The name to test
        test_pointer: ROM address to use for testing (should be safe area)

    Returns:
        True if round-trip is successful, False otherwise
    """
    # Write compressed name
    write_compressed_name(test_pointer, name)

    # Read it back
    result = read_compressed_name(test_pointer)

    # Check if they match (accounting for null terminator)
    expected = name.encode("ascii") + END
    return result == expected
