"""Throwaway: build the M5 emulator check ROMs (baseline and with the edits). Not committed."""

import shutil
import sys
from pathlib import Path

EDIT = "--edits" in sys.argv
if EDIT:
    sys.argv.remove("--edits")

source = Path("__main__.py").read_text(encoding="utf-8").split('if __name__ == "__main__":')[0]
ns: dict[str, object] = {"__name__": "iris_main"}
exec(compile(source, "__main__.py", "exec"), ns)  # noqa: S102
# Start with what the checks need: Potions and Speed potions (HER-192), and the Light knife, whose IP Light attack uses effect $09 (HER-194).
from lookups.items import Items  # noqa: E402
_hook = ns["apply_new_game_hook"]
ns["apply_new_game_hook"] = lambda **kw: _hook(**kw, start_items=[(Items.POTION, 9), (Items.SPEED_POTION, 9), (Items.LIGHT_KNIFE, 1)])  # type: ignore[operator]
ns["main"]()  # type: ignore[operator]

from enums.flags import Usability  # noqa: E402
from helpers.files import new_file, save, write_file  # noqa: E402
from scripting.core import Instruction, listing  # noqa: E402
from structures.ip_effect import IPEffect  # noqa: E402
from structures.item import Item  # noqa: E402
from structures.spell import Spell  # noqa: E402

report = []
if EDIT:
    # HER-193: Flash base damage $41 -> $200, element $0800 (thunder) -> $0002 (fire).
    flash = Spell.from_index(0)
    damage = next(i for i in flash.code.body if isinstance(i, Instruction) and i.opcode == 0x22)
    damage.operands = [0x0002, 0x0200, *damage.operands[2:]]
    flash.write()
    report.append(f"Flash:\n{listing(Spell.reread(0).code)}")

    # HER-194: Light attack (the Light knife's IP, effect $09): damage base reg $80 (ATP x 1.5) -> constant 1.
    # Same size: the IP effect table is packed and can't grow until it may move (HER-199).
    light = IPEffect.from_index(0x09)
    report.append(f"Light attack before:\n{listing(light.code)}")
    hit = next(i for i in light.code.body if isinstance(i, Instruction) and i.opcode == 0x21)
    hit.operands = [hit.operands[0], 0x0001, *hit.operands[2:]]
    light.write()
    report.append(f"Light attack after:\n{listing(IPEffect.reread(0x09).code)}")

    # HER-192: Potion's battle effect grows (HP and MP); Speed potion gains a battle effect (Potion's heal).
    potion = Item.from_index(2)
    heal = Instruction(0x24, [0x00, 0x1E, 0x00, 0x0B])
    potion.replace_script("battle", [heal, Instruction(0x24, [0x01, 0x1E, 0x00, 0x0B])])
    potion.write()
    speed = Item.from_index(20)
    speed.replace_script("battle", [Instruction(0x24, [0x00, 0x1E, 0x00, 0x0B])])
    speed.usability = Usability(speed.usability | Usability.USABLE_BATTLE)
    speed.properties[13] = potion.properties[13]  # battle animation; without it the game plays the attack animation
    speed.write()
    for index in (2, 20):
        item = Item.reread(index)
        report.append(f"{item.name_pointer.name!r} flags={item.flags():#06x} at {item.pointer:#x}:\n{listing(item.code)}")  # type: ignore[arg-type]

write_file.flush()
name = "m5-checks-v3" if EDIT else "m5-baseline-v3"
target = new_file.with_name(f"{name}-{new_file.stem.rsplit('-', 1)[1]}.smc")
save(target)
Path("m5_check_report.txt").write_text("\n".join(report), encoding="utf-8")
print(target)  # noqa: T201
