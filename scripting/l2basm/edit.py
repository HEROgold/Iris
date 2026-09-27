"""Editing parsed L2BASM scripts: which instructions an entry reaches, and replacing one entry's code."""

from scripting.core import Flow, Instruction, Item, Label, Script


def _label_index(script: Script) -> dict[str, int]:
    return {item.name: i for i, item in enumerate(script.body) if isinstance(item, Label)}


def reachable(script: Script, entry: str) -> set[int]:
    """Body indices of the instructions reachable from label ``entry``."""
    labels = _label_index(script)
    if entry not in labels:
        raise KeyError(entry)
    seen: set[int] = set()
    stack = [labels[entry]]
    while stack:
        i = stack.pop()
        while i < len(script.body) and i not in seen:
            item = script.body[i]
            if not isinstance(item, Instruction):
                i += 1
                continue
            seen.add(i)
            spec = script.language.spec(item.opcode)
            jumps = [labels[v.name] for v in item.operands if isinstance(v, Label) and v.name in labels]
            if spec.flow is Flow.END:
                break
            if spec.flow is Flow.GOTO:
                if not jumps:
                    break
                i = jumps[0]
                continue
            if spec.flow is Flow.BRANCH:
                stack.extend(jumps)
            i += 1
    return seen


def replace_entry(script: Script, entry: str, items: list[Item]) -> None:
    """Remove what only ``entry`` reaches, then put ``items`` right after the ``entry`` label.

    Instructions another entry label also reaches stay. Labels stay in place (a label nothing jumps to costs no bytes).
    Unreached Data stays too, so bytes between blocks are kept unless the caller removes them.

    When the entry label sits inside another entry's path (a shared block the other entry falls through or jumps
    into), putting ``items`` there would run them on that path too. Then the entry label moves to the end of the body
    with ``items`` after it; ``items`` end with an END (see ``block``), so nothing falls through past them.
    """
    others = [
        item.name for item in script.body if isinstance(item, Label) and item.name != entry and not item.name.startswith("L_")
    ]
    keep: set[int] = set()
    for name in others:
        keep |= reachable(script, name)
    drop = reachable(script, entry) - keep
    at = _label_index(script)[entry]
    following = next((i for i in range(at + 1, len(script.body)) if isinstance(script.body[i], Instruction)), None)
    move = following is not None and following in keep
    new_body: list[Item] = []
    for i, item in enumerate(script.body):
        if i in drop:
            continue
        if isinstance(item, Label) and item.name == entry:
            if move:
                continue
            new_body.append(item)
            new_body.extend(items)
            continue
        new_body.append(item)
    if move:
        new_body.extend([Label(entry), *items])
    script.body = new_body
