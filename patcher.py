import shutil
import struct
from os.path import getsize
from pathlib import Path

from bitstring import BitArray

from args import args
from enums.patches import Patch
from helpers.files import new_file
from helpers.files import BackupFile
from patches.parser import PatchData, PatchParser
from structures.item import Item

from logger import iris
from helpers.addresses import address_from_lorom
from structures.zone import Zone





def apply_patch(patch: Patch) -> Path:
    """
    Applies a given patch to the file.

    Parameters
    -----------
    :param:`patch`: :class:`Patch`
        The patch to apply

    Returns
    -------
    :class:`Path`
        The path to the patched file.
    :class:`bool`
        True if the patch was applied, False if not.

    Raises
    ------
    :class:`NotImplementedError`
        Error when a given patch is not implemented.
    """
    # Vanilla > Fixxxer Deluxe > Frue > Spekkio, Kureji 
    iris.info(f"Applying patch {patch.name}")
    if patch == Patch.VANILLA:
        return new_file
    patch_dir = Path(__file__).parent/"patches"
    if patch == Patch.FRUE:
        patch_dir = patch_dir/"Lufia2_-_Frue_Lufia_v7"
        patch_file = patch_dir/"Frue_Lufia_v7.ips"
    elif patch == Patch.SPEKKIO:
        patch_dir = patch_dir/"Lufia2_-_Spekkio_Lufia_v7"
        patch_file = patch_dir/"Spekkio_Lufia_v7.ips"
    elif patch == Patch.KUREJI:
        patch_dir = patch_dir/"Lufia2_-_Kureji_Lufia_v7"
        patch_file = patch_dir/"Kureji_Lufia_difficult_with_normal_enemy_buff_v7.ips"
    else:
        raise NotImplementedError(f"Patch {patch.name} not implemented.")
    return patch_files(Path(args.file), patch_file)


def patch_files(rom: Path, patch: Path):
    # Backup original ROM
    original = rom
    suffix = rom.suffix
    header = False # We remove the header immediately after converting the rom.
    rom = original.with_suffix(".tmp")
    shutil.copy(original, rom)

    iris.debug(f"Applying patch {patch=} to {rom=}.")
    iris.debug(f"{original=}")
    iris.debug(f"{patch=}")
    iris.debug(f"{rom=}")


    with patch.open("rb") as pf, rom.open("r+b") as rf:
        patch_size = getsize(patch)
        if pf.read(5) != b"PATCH":
            raise Exception("Invalid patch header.")
        # Read First Record
        r = pf.read(3)
        while pf.tell() not in [patch_size, patch_size - 3]:
            # Unpack 3-byte pointers.
            offset = unpack_int(r)
            if not header:
                offset -= 512
            # Read size of data chunk
            r = pf.read(2)
            size = unpack_int(r)

            if size == 0:  # RLE Record
                r = pf.read(2)
                rle_size = unpack_int(r)
                data = pf.read(1) * rle_size
            else:
                data = pf.read(size)

            if offset >= 0:
                # Write to file
                rf.seek(offset)
                rf.write(data)
            # Read Next Record
            r = pf.read(3)

        if patch_size - 3 == pf.tell():
            trim_size = unpack_int(pf.read(3))
            rf.truncate(trim_size)

    # Remove backup
    new = rom.with_stem(f"{rom.stem}-{args.seed}").with_suffix(suffix)
    shutil.copy(rom, new)
    rom.unlink()
    iris.info("Patch applied.")
    return new


def unpack_int(string: bytes):
    """Read an n-byte big-endian integer from a byte string."""
    (ret,) = struct.unpack_from('>I', b'\x00' * (4 - len(string)) + string)
    return ret


# event_parser = EventPatchParser()  # Script parser for event patches.
parser = PatchParser()  # Script parser for patches.

# Mapping table for SNES Game Genie characters to hexadecimal values
genie_translation_table = {
    "D": 0x0, "F": 0x1, "4": 0x2, "7": 0x3, "0": 0x4,
    "9": 0x5, "1": 0x6, "5": 0x7, "6": 0x8, "B": 0x9,
    "C": 0xA, "8": 0xB, "A": 0xC, "2": 0xD, "3": 0xE, "E": 0xF,
}

genie_address_encrypted = "ijklqrstopabcduvwxefghmn"
genie_address_decrypted = "abcdefghijklmnopqrstuvwx"

def validate_genie_code(code: str):
    for char in code:
        if char not in genie_translation_table:
            raise ValueError(f"Invalid Game Genie character {char}")

def translate_genie_code_chars(code: str) -> list[int]:
    translated_code = [
        genie_translation_table[char]
        for char in code
        if char in genie_translation_table
    ]
    return translated_code

def test_translate_genie_code_chars():
    code = "ABCD-EFFF"
    code = code.replace("-", "")
    address, data = translate_game_genie_code_snes(code)

    assert address == 0xC4A704, f"Expected 0xC4A704, got {address:x}"
    assert data == 0xC9, f"Expected 0xC9, got {data:x}"


def translate_game_genie_code_snes(code: str) -> tuple[int, int]:
    """Translate a 8 sized SNES Game Genie code to a patch."""
    iris.debug(f"Translating Game Genie code {code}")
    validate_genie_code(code)
    n0, n1, n2, n3, n4, n5, n6, n7 = translate_genie_code_chars(code)
    data = (n0 << 4) + n1

    h1 = (n2 << 4) + n3
    h2 = (n4 << 4) + n5
    h3 = (n6 << 4) + n7

    _b = BitArray(bytes((h1, h2, h3))).bin

    encoded: dict[str, str] = {}
    decoded: list[str] = []
    address: list[BitArray] = []
    for i, v  in enumerate(_b):
        encoded[genie_address_encrypted[i]] = v
    for i, v in enumerate(genie_address_decrypted):
        decoded.append(encoded[v])

    binary_address = decoded[0:8], decoded[8:16], decoded[16:24]
    for i in binary_address:
        t = "".join(i)
        address.append(BitArray(bin=t))

    ret_address = address[0] + address[1] + address[2]
    return ret_address.uint, data


def apply_game_genie_codes(*codes: str):
    """Apply any game genie code to the rom.
    https://gamefaqs.gamespot.com/boards/588451-lufia-ii-rise-of-the-sinistrals/80223211
    Contains a lot of codes to use. (Needs a LOT of testing, and confirmation)
    """
    if codes == ("",):
        return
    for code in codes:
        code = code.replace("-", "").upper()
        address, data = translate_game_genie_code_snes(code)
        address = address_from_lorom(address)

        # Empty validation, Unable to validate arbitrary Game Genie codes.
        validation = {(address, None): bytearray([])}
        patch = {
            (address, None): bytearray([data]),
        }

        verify_patch(patch, validation)  # type: ignore[reportArgumentType]
        write_patch(patch, validation, no_verify=True)  # type: ignore[reportArgumentType]
        verify_after_patch(patch)  # type: ignore[reportArgumentType]

# TODO: Write a function that can apply SRAM patches.

# TODO: get a event patch's bytecode diff and apply it to the rom.
# def max_world_clock():
#     file = Path(__file__).parent/"patches/eventpatch_max_world_clock.txt"
#     _patch, _validation = event_parser(file)
#     patch, validation = parser(file)
# def open_world_base() -> None:
#     file = Path(__file__).parent/"patches/eventpatch_open_world_base.txt"
#     _patch, _validation = event_parser(file)
#     patch, validation = parser(file)
# def skip_tutorial():
#     file = Path(__file__).parent/"patches/eventpatch_skip_tutorial.txt"
#     _patch, _validation = event_parser(file)
#     patch, validation = parser(file)
# def treadool_warp():
#     file = Path(__file__).parent/"patches/eventpatch_treadool_warp.txt"
#     _patch, _validation = event_parser(file)
#     patch, validation = parser(file)


def start_engine():
    item = Item.from_index(449)
    assert item.name_pointer.name.startswith("Engine"), f"Expected Engine, got {item.name_pointer}"
    # TODO: add that to starting inventory.

def set_spawn_location(location: Zone, entrance_cutscene: int = 0x2):
    # entrance_cutscene
    # Unused/unknown values (by the game) crash the game.
    # 01 Game ending cutscene. (for every zone?)
    # 02 (first time entry for every zone?) > Forfeit Island starts a battle.

    # Cutscene flag/index

    # 0x01adab: 0xa9 0xa0
    # 0x01adb3: 0xa9 0x0f

    # VALIDATION
    # 0x01adab: 0xa9 0x03
    # 0x01adb3: 0xa9 0x02
    iris.debug(f"Setting spawn location to {location.name=}, with {entrance_cutscene=}")
    patch = {
        (0x01adab, None): bytearray(b'\xa9') + bytearray(location.index.to_bytes()),
        (0x01adb3, None): bytearray(b'\xa9') + bytearray(entrance_cutscene.to_bytes())
    }
    validation = {
        (0x01adab, None): bytearray(b'\xa9\x03'),
        (0x01adb3, None): bytearray(b'\xa9\x02')
    }

    verify_patch(patch, validation)  # type: ignore[reportArgumentType]
    write_patch(patch, validation)  # type: ignore[reportArgumentType]
    verify_after_patch(patch)  # type: ignore[reportArgumentType]


def apply_absynnonym_patch(name: str):
    file = Path(__file__).parent/f"patches/absynnonym/patch_{name}.txt"
    iris.debug(f"Patching {file.name}")

    patch, validation = parser(file)
    verify_patch(patch, validation)
    write_patch(patch, validation, no_verify=True)
    verify_after_patch(patch)


def verify_patch(patch: PatchData, validation: PatchData):
    # Check if Validation is same as expected data. (before patching)
    iris.debug(f"Verifying patch. {patch=}, {validation=}")
    with BackupFile(new_file) as backup, backup.open("rb") as file:
        for (address, _), code in sorted(validation.items()):
            file.seek(address)
            written = file.read(len(code))
            if code != written:
                raise Exception(f"Validation {address:x} conflicts with unmodified data.")


def verify_after_patch(patch: PatchData):
    # Apply patch, then check if it is the same as the expected data.
    iris.debug(f"Verifying after patch. {patch=}")
    with BackupFile(new_file) as backup, backup.open("rb") as file:
        for (address, _), code in sorted(patch.items()):
            file.seek(address)
            written = file.read(len(code))
            if code != written:
                raise Exception(f"Patch {address:x} conflicts with modified data.")


def write_patch(patch: PatchData, validation: PatchData, no_verify: bool = False):
    iris.debug(f"Writing patch. {patch=}, {validation=}")
    with BackupFile(new_file) as backup, backup.open("rb+") as f:
        for patch_dict in (validation, patch):
            for (address, _), code in sorted(patch_dict.items()):
                f.seek(address)

                if patch_dict is validation:
                    validate = f.read(len(code))
                    if validate != code[:len(validate)]:
                        error = f'Patch {patch:s}-{address:x} did not pass validation.'
                        if no_verify:
                            print(f'WARNING: {error:s}')
                        else:
                            raise Exception(error)
                else:
                    assert patch_dict is patch
                    iris.debug(f"Writing {code=} to {address=}")
                    f.write(code) # type: ignore[reportArgumentType]
