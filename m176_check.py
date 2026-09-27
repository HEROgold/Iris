"""Throwaway: build the HER-176 emulator check ROMs (--start-capsule on current code). Not committed.

Run with the normal CLI flags plus --start-capsule. Checks that the start_capsule hook's code, placed by asar's
freecode, still holds the same bytes at the end of the build (later structure writes must not land on it).
"""

import shutil
import sys
from pathlib import Path

NAME = sys.argv.pop(sys.argv.index("--name") + 1)
sys.argv.remove("--name")

source = Path("__main__.py").read_text(encoding="utf-8").split('if __name__ == "__main__":')[0]
ns: dict[str, object] = {"__name__": "iris_main"}
exec(compile(source, "__main__.py", "exec"), ns)  # noqa: S102

from helpers.addresses import address_from_lorom  # noqa: E402
from helpers.files import new_file, save, write_file  # noqa: E402

HOOK = 0x1AD80  # $83:AD80, the new game's capsule check that start_capsule.asm hooks
HOOK_BODY = 0x100
snapshot: dict[str, bytes | int] = {}
_start_capsule = ns["start_capsule"]


def start_capsule_and_snapshot(*args: object, **kwargs: object) -> None:
    _start_capsule(*args, **kwargs)  # type: ignore[operator]
    write_file.flush()
    write_file.seek(HOOK)
    jump = write_file.read(4)
    assert jump[0] in {0x5C, 0x22}, f"no JML/JSL at $83:AD80: {jump.hex()}"
    target = address_from_lorom(int.from_bytes(jump[1:4], "little"))
    write_file.seek(target)
    snapshot.update(target=target, body=write_file.read(HOOK_BODY))


ns["start_capsule"] = start_capsule_and_snapshot
ns["main"]()  # type: ignore[operator]

write_file.flush()
target = snapshot["target"]
assert isinstance(target, int)
write_file.seek(target)
final = write_file.read(HOOK_BODY)
changed = [i for i, (a, b) in enumerate(zip(snapshot["body"], final, strict=True)) if a != b]  # type: ignore[arg-type]
print(f"start_capsule hook body at {target:#x}: {'intact' if not changed else f'CHANGED at +{changed[:8]}'}")  # noqa: T201

out = new_file.with_name(f"{NAME}-{new_file.stem.rsplit('-', 1)[1]}.smc")
save(out)
print(out)  # noqa: T201
