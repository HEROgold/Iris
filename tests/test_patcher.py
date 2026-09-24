"""``apply_patch`` must patch the per-seed output in place, keeping writes that happened before it ran."""

from enums.patches import Patch
from helpers.files import write_file
from patcher import apply_patch
from tests.reset_file import reset_file


ROM_NAME = 0x7FC0  # SNES header title; none of the IPS base patches touch it.
FRUE_SIZE = 0x400000


def test_apply_patch_keeps_earlier_writes() -> None:
    try:
        write_file.seek(ROM_NAME)
        write_file.write(b"IRIS-MARKER")
        write_file.flush()  # an earlier patch's write that has already reached the disk
        apply_patch(Patch.FRUE)
        write_file.flush()
        write_file.seek(ROM_NAME)
        assert write_file.read(11) == b"IRIS-MARKER"
    finally:
        reset_file()


def test_apply_patch_applies_the_ips_to_the_output() -> None:
    try:
        apply_patch(Patch.FRUE)
        write_file.flush()
        assert write_file.seek(0, 2) == FRUE_SIZE
        # FRUE renames capsule 7 (Cupid -> Rookie Angel) in the capsule table's record.
        write_file.seek(0xBE038)
        assert write_file.read(12).startswith(b"Rookie Angel")
    finally:
        reset_file()
