import os
from pathlib import Path

type PatchData = dict[tuple[int, str | None], bytearray | str]

class PatchParser:
    """Returns bytecode from a patch file, in a tuple. The patch bytecode, and validation bytecode."""

    def __call__(self, patch_file: Path) -> tuple[PatchData, PatchData]:
        patch: PatchData = {}
        validation: PatchData = {}
        definitions: dict[str, str] = {}
        labels: dict[str, tuple[int, str | None] | None] = {}
        next_address: int
        file_name: str | None = None
        read_into = patch

        if not patch_file.name.startswith("patch_"):
            raise Exception(f"Patch file {patch_file} must start with 'patch'.")

        f = open(patch_file)

        for line in f:
            line = line.strip()
            if "#" in line:
                line = line.split("#")[0].strip()

            if not line:
                continue

            while "  " in line:
                line = line.replace("  ", " ")

            if line.startswith(".def"):
                _, name, value = line.split(" ", 2)
                definitions[name] = value
                continue

            if line.startswith(".label"):
                _, name = line.split(" ")
                address = None
                labels[name] = None
                continue

            for name in sorted(definitions, key=lambda d: (-len(d), d)):
                if name in line:
                    line = line.replace(name, definitions[name])

            if line.upper() == "VALIDATION":
                read_into = validation
                continue

            if ":" not in line:
                line = ":" + line

            address, code = line.split(":")
            address = address.strip()
            if not address:
                address = next_address  # noqa: F821 # type: ignore[reportPossiblyUnboundVariable]
            else:
                if "@" in address:
                    address, file_name = address.split("@")
                    file_name = file_name.replace("/", os.path.sep)
                    file_name = file_name.replace("\\", os.path.sep)
                address = int(address, 0x10)
            code = code.strip()
            while "  " in code:
                code = code.replace("  ", " ")

            if (address, file_name) in read_into:
                raise Exception(f"Multiple {address:x} patches used.")
            if code:
                read_into[(address, file_name)] = code
            for name in labels:
                if labels[name] is None:
                    labels[name] = (address, file_name)

            next_address = address + len(code.split())

        for read_into in (patch, validation):
            for address, file_name in sorted(read_into):
                code = read_into[address, file_name]
                for name in sorted(labels, key=lambda i: (-len(i), i)):
                    if name in code:  # type: ignore[reportOperatorIssue] code is str here.
                        if a := labels[name]:
                            target_address, target_filename = a
                            assert target_filename == file_name
                            jump = target_address - (address + 2)
                            if jump < 0:
                                jump = 0x100 + jump
                            if not 0 <= jump <= 0xFF:
                                raise Exception(
                                    f"Label out of range {address} - {code}"
                                )
                            code = code.replace(name, f"{jump:x}")  # type: ignore[reportArgumentType]

                code = bytearray(map(lambda s: int(s, 0x10), code.split()))
                read_into[address, file_name] = code

        f.close()
        return patch, validation
