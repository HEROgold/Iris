"""Inventory every event-script item grant (opcodes 0x20 / 0x21) as a markdown report.

Run from the ``src`` directory with a vanilla ROM::

    python tools/dump_item_grants.py --file <vanilla-rom> --vanilla [--out docs/ap/item_grants.md]

``--file`` / ``--vanilla`` are consumed by ``args``; ``--out`` is read from ``sys.argv`` here and
stripped before Iris parses its arguments. A grant is ``flagged`` when the same script contains a
set-event-bit instruction (opcode 0x1A); the flag numbers are listed. The address is the headerless
ROM address of the item operand byte, read back from the ROM to verify it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OUT = None
if "--out" in sys.argv:
    i = sys.argv.index("--out")
    OUT = sys.argv[i + 1]
    del sys.argv[i : i + 2]

from enums.flags import EventFlag  # noqa: E402
from helpers.files import read_file  # noqa: E402
from structures.event_script import MapEvent  # noqa: E402
from structures.event_script.dump import _signature  # noqa: E402
from structures.item import Item  # noqa: E402
from tables import MapEventObject  # noqa: E402

SET_FLAG = 0x1A
GRANT_OPS = {0x20: 0x000, 0x21: 0x100}


def collect() -> tuple[list[dict], int]:
    rows: list[dict] = []
    mismatches = 0
    for i in range(MapEventObject.count):
        m = MapEvent.from_index(i)
        m.read()
        map_name = m.clean_map_name.decode("ascii", errors="replace").strip()
        for event_list in m.event_lists:
            for script in event_list.events:
                flags = [int(ins.operands[0]) for ins in script.instructions if ins.opcode == SET_FLAG]
                for ins in script.instructions:
                    if ins.opcode not in GRANT_OPS:
                        continue
                    raw, count = int(ins.operands[0]), int(ins.operands[1])
                    address = script.pointer + ins.line + 1
                    read_file.seek(address)
                    if read_file.read(1)[0] != raw:
                        mismatches += 1
                    item = GRANT_OPS[ins.opcode] + raw
                    rows.append(
                        {
                            "map": m.index,
                            "map_name": map_name,
                            "sig": _signature(m.index, script),
                            "addr": address,
                            "item": item,
                            "name": Item.from_index(item).name_pointer.name.strip(),
                            "count": count,
                            "flags": flags,
                        }
                    )
    return rows, mismatches


def flag_text(flags: list[int]) -> str:
    return ", ".join(f"{f} ({EventFlag.name_of(f)})" for f in flags)


def render(rows: list[dict], mismatches: int, command: str) -> str:
    flagged = [r for r in rows if r["flags"]]
    key = [r for r in rows if 423 <= r["item"] <= 466]
    npc = [r for r in rows if r["sig"].split("-")[1] == "X"]
    lines = [
        "# Event-script item grants",
        "",
        "Every `0x20 XX YY` (item `0x00XX`) and `0x21 XX YY` (item `0x01XX`) instruction in the vanilla event scripts.",
        "`flagged` means the same script contains a set-event-bit (`0x1A`) instruction; its flag numbers are listed.",
        "Address is the headerless ROM address of the item operand byte (read back from the ROM and verified).",
        "",
        f"Generated with: `{command}`",
        "",
        f"- Grants: {len(rows)}",
        f"- Distinct items: {len({r['item'] for r in rows})}",
        f"- Flagged: {len(flagged)}; unflagged: {len(rows) - len(flagged)}",
        f"- Key items (423-466) granted: {len(key)}",
        f"- Grants in NPC-load scripts (class X): {len(npc)}",
        f"- Address readback mismatches: {mismatches}",
        "",
        "| Map | Map name | Script | Address | Item | Item name | Count | Flag | Flag numbers |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted(rows, key=lambda r: (r["map"], r["sig"], r["addr"])):
        lines.append(
            f"| {r['map']:02X} | {r['map_name']} | {r['sig']} | {r['addr']:06X} | {r['item']} | {r['name']} "
            f"| {r['count']} | {'flagged' if r['flags'] else 'unflagged'} | {flag_text(r['flags'])} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    rows, mismatches = collect()
    text = render(rows, mismatches, "python tools/dump_item_grants.py --file <vanilla-rom> --vanilla --out docs/ap/item_grants.md")
    if OUT:
        with open(OUT, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    else:
        print(text)
