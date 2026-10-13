"""A grant's "Gets ..." message names the item its ``20``/``21`` gives (Iris-Dev#52).

The linear base patch keeps each AP grant's vanilla message in a fixed-size slot; the world writes the grant's item
and, for another item, "Gets <name>." over the slot (``lufia2ow/grant_text.py``); the AP item says who it's for
(Iris-Dev#19). These build the base ROM, write a
seed's tokens the way the world does and read every grant script back.
"""

import importlib.util
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest
from iris.build import build
from iris.enums.patches import Patch
from iris.helpers import files
from iris.helpers.files import open_rom, output_bytes, session, use, write_file
from iris.patches.archipelago.overworld.ap_item import AP_ITEM_INDEX
from iris.patches.archipelago.overworld.grant_text import (
    GRANT_TEXTS,
    MESSAGE_SIZE,
    NEUTRAL_LINES,
    PAUSE_TAG,
    TEXT_WINDOW,
    text_slots,
)
from iris.structures.event_script.codec import render_text
from iris.structures.event_script.containers import reset_map_events
from iris.structures.event_script.instructions import Instruction, TextChunk
from iris.tables import select, selected


pytest.importorskip("bsdiff4")

from tools.build_ap_basepatch import OPTIONS, vanilla_image
from tools.dump_item_grants import GRANT_OPS
from tools.export_ap_data import _grants, _moved, _script, _shown_names


WORLD_GRANT_TEXT = Path(__file__).resolve().parents[2] / "lufia2ow" / "grant_text.py"
POTION = 2
FIRE_ARROW = 426
"""Above 0xFF: the grant becomes opcode 0x21."""
REMOTE_ITEM, REMOTE_PLAYER = "Master Sword of the Ages", "Tester2"
REMOTE_MESSAGE = "Found Master Sword of\nfor Tester2."


def _world_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("grant_text", WORLD_GRANT_TEXT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def restore() -> Iterator[None]:
    rom, patch = session(), selected()
    yield
    select(patch)
    use(rom)


def _vanilla_messages(image: bytes) -> dict[str, str]:
    """Each slot grant's vanilla "Gets ..." message, by signature."""
    select(Patch.VANILLA)
    open_rom(image)
    return {grant.signature: _message(grant.map_index, grant.signature) for grant in GRANT_TEXTS}


def _texts(instruction: Instruction) -> list[TextChunk]:
    chunks = instruction.operands[0]
    assert isinstance(chunks, list)
    return chunks


def _message(map_index: int, signature: str) -> str:
    """The script's "Gets ..." (or a remote item's "Found ...") message as it shows: no position, END MESSAGE or pauses,
    no trailing space."""
    script = _script(map_index, signature)
    found = [
        render_text([chunk for chunk in _texts(ins) if chunk.tag not in {"POSITION", 0x01}]).replace(PAUSE_TAG, "")
        for ins in script.instructions
        if ins.opcode == TEXT_WINDOW
    ]
    gets = [text.rstrip(" ") for text in found if text.startswith(("Gets", "Found"))]
    assert len(gets) == 1, f"{signature}: {gets}"
    return gets[0]


def _given(map_index: int, signature: str, n: int) -> int:
    script = _script(map_index, signature)
    grant = [ins for ins in script.instructions if ins.opcode in GRANT_OPS][n]
    return GRANT_OPS[grant.opcode] + int(grant.operands[0])


def _base() -> tuple[bytes, dict[str, str], list]:
    image = vanilla_image(files.original_file)
    vanilla = _vanilla_messages(image)
    grants = _grants()
    build(image, OPTIONS)
    return image, vanilla, _moved(grants, open_world=False)


@pytest.mark.usefixtures("restore")
def test_base_patch_keeps_the_vanilla_messages() -> None:
    _, vanilla, _ = _base()
    reset_map_events()
    assert {grant.signature: _message(grant.map_index, grant.signature) for grant in GRANT_TEXTS} == vanilla


@pytest.mark.usefixtures("restore")
def test_slots_fit_every_name() -> None:
    _base()
    names = _shown_names(output_bytes())
    world = _world_module()
    assert max(len(name) for name in names) + len("Gets .") <= MESSAGE_SIZE
    for slot in text_slots():
        assert slot.size >= MESSAGE_SIZE
        assert len(world.message(max(names, key=len), slot.size)) == slot.size
        assert len(world.remote_message("x" * 40, "y" * 40, slot.size)) == slot.size


@pytest.mark.usefixtures("restore")
def test_seed_messages_name_the_granted_item() -> None:
    """A seed with another item at every slot grant: the local Potion, the AP item (another player's item, Iris-Dev#19)
    and the Fire arrow (0x21)."""
    _, _, grants = _base()
    names = _shown_names(output_bytes())
    world = _world_module()
    slots = {(slot.signature, slot.item): slot for slot in text_slots()}
    placed = {}
    for n, (_, signature, offset, item, _, _) in enumerate(grants):
        slot = slots.get((signature, item))
        if slot is None:
            continue
        new = (POTION, AP_ITEM_INDEX, FIRE_ARROW)[n % 3]
        opcode = 0x21 if new & 0x100 else 0x20
        write_file.seek(offset - 1)
        write_file.write(bytes([opcode, new & 0xFF]))
        write_file.seek(slot.offset)
        if new == AP_ITEM_INDEX:
            write_file.write(world.remote_message(REMOTE_ITEM, REMOTE_PLAYER, slot.size))
        else:
            write_file.write(world.message(names[new], slot.size))
        placed[signature] = new
    assert len(placed) == len(GRANT_TEXTS)
    reset_map_events()
    order: dict[str, int] = {}
    for map_index, signature, _, item, _, _ in grants:
        n = order.get(signature, 0)
        order[signature] = n + 1
        if signature not in placed or (signature, item) not in slots:
            continue
        given = _given(map_index, signature, n)
        assert given == placed[signature]
        expected = REMOTE_MESSAGE if given == AP_ITEM_INDEX else f"Gets {names[given]}."
        assert _message(map_index, signature) == expected


@pytest.mark.usefixtures("restore")
def test_pickup_lines_are_neutral() -> None:
    _base()
    reset_map_events()
    for line in NEUTRAL_LINES:
        texts = [
            render_text(_texts(ins))
            for ins in _script(line.map_index, line.signature).instructions
            if ins.operands and isinstance(ins.operands[0], list)
        ]
        assert not any(line.old in text for text in texts), line
        assert any(line.new in text for text in texts), line
