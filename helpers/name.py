from bitstring import BitArray

from helpers.addresses import address_from_lorom
from helpers.files import read_file, restore_pointer, write_file


END = b"\x00"
COMPRESS = b"\x0A"
COMPRESSED_NAME_OFFSET = 0x878000

def read_compressed_name(pointer: int):
    read_file.seek(pointer)
    name = b""
    while True:
        name += read_file.read(1)
        if name.endswith(b"\x00"):
            break
    return name


def read_as_decompressed_name(pointer: int):
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


def write_compressed_better(end_pointer: int, name: bytes) -> None:
    split = 0
    # name_len = len(name)
    for i, byte in enumerate(reversed(name)):
        if byte == 0x0A:
            split = -i + 2 # + 2 # 0A + 2 bytes
            break

    rest, write = name[:split], name[split:]
    write_length = len(write)
    write_file.seek(end_pointer - write_length)
    write_file.write(write)


    while rest:
        write_file.seek(end_pointer - (write_length + len(rest)))
        # print(rest)

        # TODO: implement sliding window for this while loop.
        # Find the address and length of the referenced word.

        if len(rest) == 3:
            # oxOa + 2 bytes, TODO: Verify
            write_file.write(rest[:0])
            break
        rest = rest[1:]
    # Read `rest` and find the address and byte length, then point/write to it.
    # TODO: Implement this part.


def find_word_address(target: bytes):
    tell = write_file.tell()
    read = write_file.read(1)
    length = len(target)
    while read != target:
        write_file.seek(tell - 1)
        read = write_file.read(length)
        tell = write_file.tell() - length
    return tell


def write_as_compressed_name(end_pointer: int, name: str) -> None:
    """Write the name to the ROM. Also recompresses the name to the ROM."""
    # WIP:!!!
    # End pointer == start pointer for next name.
    # raise NotImplementedError
    names = name.encode("ascii").split(COMPRESS)

    # TODO: work in reverse with names
    # Multiple sections can be compressed, so we need to work in reverse.
    # Cave to Sundletan B2, in rom is 0A 5B D8 32
    # 32 here is ascii 2.
    # 0A 5B D8 references to Cave to Sundletan B
    # Which is written as 0A 53 28 20 74 6F 20 53 75 6E 64 6C 65 74 61 6E 20 42
    #               (REF TO CAVE) + _  T  O  _  S  U  N  D  L  E  T  A  N  _  B
    # (_ is a space > 0x20)
    # In that sequence, 0A 53 28 refers to Cave >Ascii 43 61 76 65

    section = names[0]

    length = 3 if section == b"" else len(section)

    write_file.seek(end_pointer - length)
    tell = write_file.tell()
    write_file.write(section)

    if len(names) == 1:
        return

    for compressed in reversed(names[:-1]):
        write_as_compressed_name(tell, compressed.decode("ascii"))

    # if len(names[-2]) == 0: # TODO: Verify, always True-thy?
    #     A0 = tell + len(names[-1]) - 4 # 3 for 0x0A + address, and 1 for 0x00 end byte.

    # for section in reversed(names[::-1]):
    #     write_file.seek(tell - 3) # -3 to point at 0x0A
    #     length = len(section)
    #     read = write_file.read(length)
    #     while read != section:
    #         write_file.seek(tell - 1)
    #         read = write_file.read(length)
    #         tell = write_file.tell() - length

    #     address = tell
    #     copy_address = address_to_lorom(address) - COMPRESSED_NAME_OFFSET
    #     bytes_1 = BitArray(uint=copy_address, length=12)
    #     bytes_2 = BitArray(uint=length - 2, length=4)
    #     to_write = (bytes_1 + bytes_2)
    #     to_write = to_write.tobytes()
    #     to_write = to_write[::-1]

    #     write_file.seek(A0)
    #     write_file.write(COMPRESS + to_write)


    # # Code for L > R
    # for section in names:
    #     if section == b"":
    #         # Sections can become empty, bc of the split on the COMPRESS byte.
    #         continue
    #     if section != names[-1]:
    #         restore = write_file.tell()
    #         length = len(section)

    #         read = write_file.read(length)
    #         tell = restore
    #         while read != section:
    #             write_file.seek(tell - 1)
    #             read = write_file.read(length)
    #             tell = write_file.tell() - length

    #         # FIXME: Something is wrong with the address calculation.
    #         # Cave to Sundletan B2 expects, 0x5bd8
    #         address = tell
    #         copy_address = address_to_lorom(address) - COMPRESSED_NAME_OFFSET
    #         bytes_1 = BitArray(uint=copy_address, length=12)
    #         bytes_2 = BitArray(uint=length - 2, length=4)
    #         to_write = (bytes_1 + bytes_2)
    #         to_write = to_write.tobytes()
    #         to_write = to_write[::-1]

    #         write_file.seek(restore)
    #         write_file.write(COMPRESS + to_write)
    #     else:
    #         write_file.write(section)
