"""Human-readable listing of a script: labels on their own lines, one instruction per line."""

from scripting.core.assembler import operand_pairs
from scripting.core.items import Data, Label, Script


def listing(script: Script) -> str:
    lines: list[str] = []
    for item in script.body:
        if isinstance(item, Label):
            lines.append(f"{item.name}:")
        elif isinstance(item, Data):
            lines.append(f"    .data {item.raw.hex(' ').upper()}")
        else:
            spec = script.language.spec(item.opcode)
            args = ", ".join(kind.render(value) for kind, value in operand_pairs(spec, item))
            lines.append(f"    {spec.name} {args}".rstrip())
    return "".join(f"{line}\n" for line in lines)
