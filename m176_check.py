"""Throwaway: build the HER-176 emulator check ROMs (--start-capsule on current code). Not committed.

Run with the normal CLI flags plus --start-capsule. Checks that the start_capsule hook's code, placed by asar's
freecode, still holds the same bytes at the end of the build (later structure writes must not land on it).
"""

import shutil
import sys
from pathlib import Path

NAME = sys.argv.pop(sys.argv.index("--name") + 1)
sys.argv.remove("--name")

import build as iris_build  # noqa: E402
from args import parse_args  # noqa: E402

from helpers.addresses import address_from_lorom  # noqa: E402
from helpers.files import save, session, write_file  # noqa: E402

HOOK = 0x1AD80  # $83:AD80, the new game's capsule check that start_capsule.asm hooks
HOOK_BODY = 0x100
snapshot: dict[str, bytes | int] = {}
_start_capsule = iris_build.start_capsule


def start_capsule_and_snapshot(*args: object, **kwargs: object) -> None:
    _start_capsule(*args, **kwargs)  # type: ignore[operator]
    write_file.flush()
    write_file.seek(HOOK)
    jump = write_file.read(4)
    assert jump[0] in {0x5C, 0x22}, f"no JML/JSL at $83:AD80: {jump.hex()}"
    target = address_from_lorom(int.from_bytes(jump[1:4], "little"))
    write_file.seek(target)
    snapshot.update(target=target, body=write_file.read(HOOK_BODY))


iris_build.start_capsule = start_capsule_and_snapshot
options = parse_args()
iris_build.build(Path(options.file), iris_build.Options.from_args(options))  # type: ignore[arg-type]

write_file.flush()
target = snapshot["target"]
assert isinstance(target, int)
write_file.seek(target)
final = write_file.read(HOOK_BODY)
changed = [i for i, (a, b) in enumerate(zip(snapshot["body"], final, strict=True)) if a != b]  # type: ignore[arg-type]
print(f"start_capsule hook body at {target:#x}: {'intact' if not changed else f'CHANGED at +{changed[:8]}'}")  # noqa: T201

out = session().source.with_name(  # type: ignore[union-attr]
    f"{NAME}-{options.seed}.smc")
save(out)
print(out)  # noqa: T201
