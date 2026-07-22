"""Golden test for the hybrid Ancient Cave basepatch.

The hybrid pipeline (native Iris item-data writes + asar-assembled ``basepatch_code.asm``) must produce a
ROM byte-identical to assembling the original, undivided ``basepatch.asm`` directly with asar. This proves
the data carved out into ``basepatch.py`` exactly covers the ``org`` blocks removed from the code ``.asm``.

Note: the repo's ``rom_diff.smc`` is a *stale* build artifact (built from an older ``basepatch.asm`` that
placed the injected code at ``$D08000`` instead of ``$9FA980`` and included since-commented-out features),
so the live ``basepatch.asm`` is the source of truth here -- not ``rom_diff.smc``.
"""

import shutil
import subprocess
from pathlib import Path

from helpers.files import new_file, original_file, write_file
from patcher import ASAR_EXE
from patches.archipelago.ancient_cave.basepatch import _ARCHIPELAGO_DIR, apply_ancient_cave_base
from tests.reset_file import reset_file


_FULL_ASM = _ARCHIPELAGO_DIR/"ancient_cave"/"basepatch.asm"


def _assemble_full_reference() -> bytes:
    """Assemble the complete, undivided basepatch.asm onto a headerless copy of the original ROM."""
    sfc = original_file.with_suffix(".acgold.sfc")
    shutil.copyfile(original_file, sfc)
    try:
        subprocess.run(  # noqa: S603
            [str(ASAR_EXE), f"-I{_ARCHIPELAGO_DIR}", "--fix-checksum=on", "--no-title-check",
             str(_FULL_ASM), str(sfc)],
            capture_output=True, text=True, check=True,
        )
        return sfc.read_bytes()
    finally:
        Path(sfc).unlink(missing_ok=True)


def test_hybrid_matches_full_asar_assembly() -> None:
    reference = _assemble_full_reference()
    try:
        apply_ancient_cave_base()
        write_file.flush()
        produced = new_file.read_bytes()
        assert produced == reference, "hybrid basepatch output differs from full-asar assembly"
    finally:
        reset_file()
