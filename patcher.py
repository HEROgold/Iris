import re
import struct
import subprocess
import tempfile
from os.path import getsize
from pathlib import Path
from typing import cast

from bitstring import BitArray

from enums.patches import Patch
from helpers.addresses import address_from_lorom
from helpers.files import output_path, write_file
from logger import iris
from patches.parser import PatchData, PatchParser
from structures.item import Item
from structures.zone import Zone


# The bundled asar assembler. We shell out to the .exe (not the DLL bindings) because the
# shipped asar.dll is 32-bit and Iris runs under 64-bit Python, so the DLL cannot be loaded.
# A subprocess is architecture-independent (WOW64).
ASAR_EXE = Path(__file__).parent/"patches"/"asar191"/"asar.exe"

parser = PatchParser()  # Script parser for patches.

def apply_asm_patch(
    asm_path: Path,
    include_dirs: list[Path] | None = None,
    *,
    fix_checksum: bool = True,
    defines: dict[str, str] | None = None,
) -> None:
    """Assemble a 65816 asar patch onto the current per-seed ROM using the bundled asar.exe.

    asar keys header detection off the file *extension*: a ``.smc`` is treated as headered, so every
    write lands 512 bytes too high and the output gains a copier header. We therefore assemble on a
    headerless ``.sfc`` copy of the session's image in a temporary directory and read the result back
    into the image, so later structure writes see asar's output (e.g. the ROM expanded to 3MB). Nothing
    is written next to the ROM.

    ``defines`` become asar ``-Dname=value`` arguments, readable in the patch as ``!name``.
    """
    if include_dirs is None:
        include_dirs = []
    with tempfile.TemporaryDirectory(prefix="iris-asar-") as tmp:
        sfc = Path(tmp)/"rom.sfc"
        write_file.seek(0)
        sfc.write_bytes(write_file.read())
        cmd = [str(ASAR_EXE), *(f"-I{d}" for d in include_dirs), *(f"-D{k}={v}" for k, v in (defines or {}).items()),
               f"--fix-checksum={'on' if fix_checksum else 'off'}", "--no-title-check", str(asm_path), str(sfc)]
        iris.debug(f"Running asar: {cmd}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603
        if result.returncode != 0:
            msg = f"asar failed to assemble {asm_path.name}:\n{result.stdout}\n{result.stderr}"
            raise RuntimeError(msg)
        data = sfc.read_bytes()
    write_file.seek(0)
    write_file.write(data)
    write_file.truncate()
    iris.info(f"Assembled {asm_path.name} ({len(data)} bytes).")


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
    # Vanilla > Frue > Spekkio, Kureji
    iris.info(f"Applying patch {patch.name}")
    if patch == Patch.VANILLA:
        return output_path()
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
        msg = f"Patch {patch.name} not implemented."
        raise NotImplementedError(msg)
    return patch_files(patch_file)


def patch_files(patch: Path) -> Path:
    """Apply an IPS ``patch`` to the per-seed output in place, through ``write_file``.

    The records go straight into the open handle, so writes made before this call (ROM name, event
    patches) survive unless the IPS itself overwrites those bytes. The IPS files target a headered ROM
    while ``write_file`` is headerless, so every record offset drops by 512.
    """
    header_size = 512
    iris.debug(f"Applying patch {patch=}.")
    records = 0
    with patch.open("rb") as pf:
        patch_size = getsize(patch)
        if pf.read(5) != b"PATCH":
            msg = "Invalid patch header."
            raise ValueError(msg)
        r = pf.read(3)
        while pf.tell() not in [patch_size, patch_size - 3]:
            offset = unpack_int(r) - header_size
            size = unpack_int(pf.read(2))
            if size == 0:  # RLE record
                rle_size = unpack_int(pf.read(2))
                data = pf.read(1) * rle_size
            else:
                data = pf.read(size)
            if offset >= 0:
                write_file.seek(offset)
                write_file.write(data)
                records += 1
            r = pf.read(3)

        if patch_size - 3 == pf.tell():
            trim_size = unpack_int(pf.read(3))
            iris.debug(f"IPS truncate {trim_size=:#08x}")
            write_file.truncate(trim_size)

    write_file.seek(0, 2)
    iris.info(f"Patch applied. {records} records written (final size {write_file.tell()} bytes).")
    return output_path()


def unpack_int(string: bytes):
    """Read an n-byte big-endian integer from a byte string."""
    (ret,) = struct.unpack_from(">I", b"\x00" * (4 - len(string)) + string)
    return ret

# Mapping table for SNES Game Genie characters to hexadecimal values
genie_translation_table = {
    "D": 0x0, "F": 0x1, "4": 0x2, "7": 0x3, "0": 0x4,
    "9": 0x5, "1": 0x6, "5": 0x7, "6": 0x8, "B": 0x9,
    "C": 0xA, "8": 0xB, "A": 0xC, "2": 0xD, "3": 0xE, "E": 0xF,
}

genie_address_encrypted = "ijklqrstopabcduvwxefghmn"
genie_address_decrypted = "abcdefghijklmnopqrstuvwx"

def validate_genie_code(code: str) -> None:
    LEN = 8
    if len(code) != LEN:
        msg = f"Invalid Game Genie code length {len(code)}, Expected {LEN}"
        raise ValueError(msg)
    for char in code:
        if char not in genie_translation_table:
            msg = f"Invalid Game Genie character {char}"
            raise ValueError(msg)

def translate_genie_code_chars(code: str) -> list[int]:
    return [
        genie_translation_table[char]
        for char in code
        if char in genie_translation_table
    ]

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
    decoded.extend(encoded[v] for v in genie_address_decrypted)

    binary_address = decoded[0:8], decoded[8:16], decoded[16:24]
    for i in binary_address:
        t = "".join(i)
        address.append(BitArray(bin=t))

    ret_address = address[0] + address[1] + address[2]
    return ret_address.uint, data


def apply_game_genie_codes(*codes: str) -> None:
    """Apply any game genie code to the rom.
    https://gamefaqs.gamespot.com/boards/588451-lufia-ii-rise-of-the-sinistrals/80223211
    Contains a lot of codes to use. (Needs a LOT of testing, and confirmation)
    """
    for raw_code in codes:
        if re.fullmatch(r"7[EF][0-9A-F]{6}", raw_code.upper()):
            msg = (
                f"{raw_code} is a Pro Action Replay RAM code ($7E/$7F); it only works in a running game "
                "and cannot be written into the ROM as a Game Genie code."
            )
            raise ValueError(msg)
        code = raw_code.replace("-", "").upper()
        address, data = translate_game_genie_code_snes(code)
        address = address_from_lorom(address)

        # Empty validation, Unable to validate arbitrary Game Genie codes.
        validation = {(address, None): bytearray([])}
        patch = {
            (address, None): bytearray([data]),
        }

        verify_patch(patch, validation)
        write_patch(patch, validation, no_verify=True)
        verify_after_patch(patch)

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


def start_engine() -> None:
    item = Item.from_index(449)
    assert item.name_pointer.name.startswith("Engine"), f"Expected Engine, got {item.name_pointer}"
    # TODO: add that to starting inventory.

def set_spawn_location(location: Zone, entrance_cutscene: int = 0x2) -> None:
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
    if entrance_cutscene not in {entrance.cutscene for entrance in location.valid_entrances}:
        msg = f"Invalid entrance cutscene {entrance_cutscene} for zone {location.name}."
        raise ValueError(msg)

    iris.debug(f"Setting spawn location to {location.name=}, with {entrance_cutscene=}")
    patch = {
        (0x01adab, None): bytearray(b"\xa9") + bytearray(location.index.to_bytes()),
        (0x01adb3, None): bytearray(b"\xa9") + bytearray(entrance_cutscene.to_bytes()),
    }
    validation = {
        (0x01adab, None): bytearray(b"\xa9\x03"),
        (0x01adb3, None): bytearray(b"\xa9\x02"),
    }

    commit_patch(patch, validation)

def commit_patch(patch: PatchData, validation: PatchData) -> None:
    """Apply a patch to the ROM file."""
    verify_patch(patch, validation)
    write_patch(patch, validation)
    verify_after_patch(patch)



def apply_absynnonym_patch(name: str) -> None:
    file = Path(__file__).parent/f"patches/absynnonym/patch_{name}.txt"
    iris.debug(f"Patching {file.name}")

    patch, validation = parser(file)
    verify_patch(patch, validation)
    write_patch(patch, validation, no_verify=True)
    verify_after_patch(patch)


def verify_patch(patch: PatchData, validation: PatchData) -> None:
    # Check if Validation is same as expected data. (before patching)
    iris.debug(f"Verifying patch. {patch=}, {validation=}")
    for (address, _), code in sorted(validation.items()):
        write_file.seek(address)
        written = write_file.read(len(code))
        if code != written:
            msg = f"Validation {address:x} conflicts with unmodified data."
            raise Exception(msg)


def verify_after_patch(patch: PatchData) -> None:
    # Apply patch, then check if it is the same as the expected data.
    iris.debug(f"Verifying after patch. {patch=}")
    for (address, _), code in sorted(patch.items()):
        write_file.seek(address)
        written = write_file.read(len(code))
        if code != written:
            msg = f"Patch {address:x} conflicts with modified data."
            raise Exception(msg)


def write_patch(patch: PatchData, validation: PatchData, no_verify: bool = False) -> None:
    iris.debug(f"Writing patch. {patch=}, {validation=}")
    for patch_dict in (validation, patch):
        for (address, _), code in sorted(patch_dict.items()):
            code = cast("bytearray", code)
            write_file.seek(address)

            if patch_dict is validation:
                validate = write_file.read(len(code))
                if validate != code[:len(validate)]:
                    error = f"Patch {patch:s}-{address:x} did not pass validation."
                    if no_verify:
                        pass
                    else:
                        raise Exception(error)
            else:
                assert patch_dict is patch
                iris.debug(f"Writing {code=} to {address=}")
                write_file.write(code)
