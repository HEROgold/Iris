"""Probe the suspected "initial EV-flag" table at ``0x1AC1A`` in the Lufia II ROM.

Reverse-engineering aid, NOT part of the randomizer. We flagged the range
``0x1AC20-0x1AC2F`` as maybe-EV-flag-related; it turns out to sit inside a 32-byte, all-zero
table ``T0 @ 0x1AC1A`` reached by the pointer table at ``0x1AC14`` (-> T0, T1, T2), right after
the single-bit mask lookup table at ``0x1AC04`` and before 65816 code at ``0x1AC7A``. That shape
matches an *initial EV-flag bitfield* copied to save-RAM on New Game (256 bits = 32 bytes,
all-zero = "no flags set at start").

We can't cheaply prove that statically (the adjacent routine doesn't read T0), so this tool writes
a unique, position-identifiable pattern across the full 32-byte T0 table, producing a probe ROM.
Boot it (with the debug menu enabled), start a New Game, read which EV flags became set, then feed
that list back via ``--decode`` to recover the exact table-byte -> flag-index mapping.

Addresses in this file are **headerless/PC file offsets** (the codebase convention). If the ROM
carries the 512-byte SNES copier header (``len % 1024 == 512``, same check as
``src/helpers/files.py``), the physical offset is shifted by ``+0x200`` and the header is preserved
in the output.

Usage::

    # write the probe (default pattern: an ascending 00..1F ramp)
    python src/tools/probe_evflags.py "Lufia II ... .smc"
    python src/tools/probe_evflags.py rom.smc --pattern ones --out rom.probe.smc
    python src/tools/probe_evflags.py rom.smc --force        # T0 already non-zero

    # after booting the probe ROM and reading the debug menu:
    python src/tools/probe_evflags.py --decode "48,49,50"    # ROM not needed for decode
"""

from __future__ import annotations

import argparse
from pathlib import Path

# --- geometry of the suspected table (headerless/PC offsets) ---------------------------------
T0_START = 0x1AC1A          # first byte of the 32-byte candidate bitfield
T0_LEN = 0x20               # 32 bytes = 256 bits
T0_END = T0_START + T0_LEN  # 0x1AC3A (exclusive) - code lives at 0x1AC7A, well clear
CODE_START = 0x1AC7A        # 65816 routine begins here; never write at/after this
HEADER_LEN = 0x200          # SNES copier header


def has_copier_header(data: bytes) -> bool:
    """True if the ROM carries the 512-byte copier header (same rule as helpers/files.py)."""
    return len(data) % 1024 == 512


def build_pattern(name: str) -> bytes:
    """Return the 32-byte payload written into T0."""
    if name == "ramp":
        # byte[i] = i -> 00 01 02 ... 1F: every byte unique (findable as a ramp in memory),
        # and each byte's set bits are decodable back to a position.
        return bytes(range(T0_LEN))
    if name == "ones":
        # all bits set: fastest yes/no + reveals the full set of flag indices in one boot.
        return b"\xff" * T0_LEN
    if name == "walkbit":
        # one walking bit per byte: best for pinning bit order within a byte over an 8-byte window.
        return bytes(1 << (i % 8) for i in range(T0_LEN))
    raise ValueError(f"unknown pattern {name!r} (choose ramp, ones, or walkbit)")


def _hexrow(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data)


def write_probe(rom_path: Path, pattern: str, out_path: Path | None, force: bool) -> Path:
    data = bytearray(rom_path.read_bytes())
    shift = HEADER_LEN if has_copier_header(data) else 0
    start = T0_START + shift
    end = T0_END + shift

    # never spill into the code that follows the tables
    assert T0_END <= CODE_START, "T0 window overlaps code region - geometry constant is wrong"

    current = bytes(data[start:end])
    print(f"header: {'yes (+0x200)' if shift else 'no'}   file size: 0x{len(data):X}")
    print(f"T0 @ 0x{T0_START:06X} (physical 0x{start:06X}), {T0_LEN} bytes")
    print(f"before: {_hexrow(current)}")

    if any(current) and not force:
        raise SystemExit(
            "refusing to write: T0 is not all-zero (already patched, wrong ROM, or a "
            "region-specific ROM). Re-run with --force if you really mean to overwrite it."
        )

    payload = build_pattern(pattern)
    assert len(payload) == T0_LEN
    data[start:end] = payload
    print(f"after:  {_hexrow(payload)}   (pattern={pattern})")

    # prove nothing outside the T0 window moved (the payload may legitimately re-write some
    # bytes to their existing value, e.g. ramp's byte 0 = 0x00, so count <= T0_LEN)
    original = rom_path.read_bytes()
    assert len(data) == len(original), "output length changed"
    changed = [i for i, (a, b) in enumerate(zip(original, data)) if a != b]
    assert all(start <= i < end for i in changed), (
        f"changed bytes outside T0 window: {[hex(i) for i in changed if not start <= i < end]}"
    )
    print(f"changed bytes: {len(changed)} (<= {T0_LEN}), all inside T0 - rest of ROM byte-identical")

    if out_path is None:
        out_path = rom_path.with_suffix(f".probe{rom_path.suffix}")
    out_path.write_bytes(data)
    print(f"wrote: {out_path}")
    return out_path


def decode(flags: list[int], pattern: str) -> None:
    """Given the EV flags the debug menu shows as SET, report the T0 byte/bit each maps to.

    The table-byte -> flag-index mapping (base offset, byte order, and bit endianness) is unknown
    until the boot confirms it, so we print both LSB-first and MSB-first interpretations of a plain
    linear mapping ``flag = byte_index*8 + bit`` and flag whether the written pattern's bit was set
    at that position.
    """
    payload = build_pattern(pattern)
    print(f"decoding {len(flags)} set flag(s) against pattern={pattern}")
    print(f"T0 payload: {_hexrow(payload)}\n")
    print(f"{'flag':>5}  {'byte':>4}  {'bit':>3}  LSB-first   MSB-first")
    for f in sorted(set(flags)):
        byte_i, bit = divmod(f, 8)
        if not (0 <= byte_i < T0_LEN):
            print(f"{f:>5}  --   (outside the 256 bits of T0)")
            continue
        val = payload[byte_i]
        lsb_set = bool(val & (1 << bit))          # bit 0 = value 0x01
        msb_set = bool(val & (1 << (7 - bit)))    # bit 0 = value 0x80
        print(
            f"{f:>5}  {byte_i:>4}  {bit:>3}  "
            f"{'SET ' if lsb_set else 'clr '}(0x{val:02X})  "
            f"{'SET ' if msb_set else 'clr '}(0x{val:02X})"
        )
    print(
        "\nInterpretation: pick the column (LSB/MSB) whose SET rows line up with the flags the "
        "debug menu actually showed. A clean match confirms T0 @0x1AC1A is the initial EV-flag "
        "bitfield and pins the mapping; no matches => T0 is not the copy source (see plan risks)."
    )


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("rom", nargs="?", type=Path, help="input ROM (.smc/.sfc); omit when using --decode")
    p.add_argument("--pattern", choices=["ramp", "ones", "walkbit"], default="ramp",
                   help="payload written into T0 (default: ramp = 00..1F)")
    p.add_argument("--out", type=Path, default=None, help="output path (default: <rom>.probe<ext>)")
    p.add_argument("--force", action="store_true", help="overwrite T0 even if it is not all-zero")
    p.add_argument("--decode", metavar="FLAGS",
                   help="comma-separated EV flag indices the debug menu showed as SET; prints the "
                        "T0 byte/bit mapping instead of writing a ROM")
    args = p.parse_args(argv)

    if args.decode is not None:
        flags = [int(x, 0) for x in args.decode.replace(" ", "").split(",") if x]
        decode(flags, args.pattern)
        return

    if args.rom is None:
        p.error("a ROM path is required unless --decode is given")
    if not args.rom.is_file():
        p.error(f"ROM not found: {args.rom}")
    write_probe(args.rom, args.pattern, args.out, args.force)


if __name__ == "__main__":
    main()
