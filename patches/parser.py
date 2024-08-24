import os
from pathlib import Path

from structures.indev.event_patcher import apply_event_patches


type PatchData = dict[tuple[int, str | None], str | bytearray | bytes]

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

class EventPatchParser:
    def __call__(self, *args, **kwargs):
        # TODOO: Bubble up (address, value) pairs for each patch.
        # TODO: Bubble (address, value) validation pairs for each patch.
        apply_event_patches(*args, **kwargs)

# Code below is the parsing of Event patch files.
# def patch_events(filenames=None, warn_double_import=True):
#     if filenames is None:
#         filenames = []
#         for label in EVENT_PATCHES:
#             filenames.append(label)
#             filename = path.join(tblpath, 'eventpatch_{0}.txt'.format(label))

#     if not filenames:
#         return

#     if not isinstance(filenames, list):
#         filenames = [filenames]
#     filenames = [fn if fn.endswith('.txt') else
#                  path.join(tblpath, 'eventpatch_{0}.txt'.format(fn))
#                  for fn in filenames]

#     patch_script_text = ''
#     for filename in filenames:
#         for line in read_lines_nocomment(filename):
#             patch_script_text += line + '\n'
#     patch_script_text = patch_script_text.strip()
#     patch_game_script(patch_script_text, warn_double_import=warn_double_import)
# def patch_game_script(patch_script_text, warn_double_import=True):
#     to_import = {}
#     identifier = None
#     script_text = None
#     for line in patch_script_text.split('\n'):
#         if '#' in line:
#             index = line.index('#')
#             line = line[:index].rstrip()
#         line = line.lstrip()
#         if not line:
#             continue
#         if line.startswith('!'):
#             line = line.strip().lower()
#             while '  ' in line:
#                 line = line.replace('  ', ' ')
#             if line.startswith('!npc'):
#                 (command, npc_index, misc, location) = line.split()
#                 map_index, location = location.split(':')
#                 a, b = location.split(',')
#                 map_index = int(map_index, 0x10)
#                 if npc_index == '+1':
#                     npc_index = None
#                 else:
#                     npc_index = int(npc_index, 0x10)
#                 try:
#                     assert misc.startswith('(')
#                     assert misc.endswith(')')
#                 except:
#                     raise Exception('Malformed "misc" field: %s' % line)
#                 misc = int(misc[1:-1], 0x10)
#                 (x, y, boundary_west, boundary_east, boundary_north,
#                     boundary_south) = None, None, None, None, None, None
#                 for axis, value_range in zip(('x', 'y'), (a, b)):
#                     try:
#                         assert '>' not in value_range
#                         if '<' in value_range:
#                             left, middle, right = value_range.split('<=')
#                             left = int(left, 0x10)
#                             middle = int(middle, 0x10)
#                             right = int(right, 0x10)
#                             assert left <= middle <= right
#                             if axis == 'x':
#                                 boundary_west = left
#                                 x = middle
#                                 boundary_east = right
#                             else:
#                                 assert axis == 'y'
#                                 boundary_north = left
#                                 y = middle
#                                 boundary_south = right
#                         else:
#                             if axis == 'x':
#                                 x = int(value_range, 0x10)
#                             else:
#                                 assert axis == 'y'
#                                 y = int(value_range, 0x10)
#                     except:
#                         raise Exception('Malformed coordinates: %s' % line)
#                 boundary = ((boundary_west, boundary_north),
#                             (boundary_east, boundary_south))
#                 MapMetaObject.get(map_index).add_or_replace_npc(
#                     x, y, boundary, misc, npc_index)
#             elif line.startswith('!exit'):
#                 try:
#                     (command, exit_index, misc,
#                         movement, dimensions) = line.split()
#                 except ValueError:
#                     (command, exit_index, misc, movement) = line.split()
#                     dimensions = '1x1'
#                 if exit_index == '+1':
#                     exit_index = None
#                 else:
#                     exit_index = int(exit_index, 0x10)
#                 try:
#                     assert misc.startswith('(')
#                     assert misc.endswith(')')
#                 except:
#                     raise Exception('Malformed "misc" field: %s' % line)
#                 misc = int(misc[1:-1], 0x10)

#                 source, destination = movement.split('->')
#                 source_index, source_location = source.split(':')
#                 dest_index, dest_location = destination.split(':')
#                 boundary_west, boundary_north = source_location.split(',')
#                 dest_x, dest_y = dest_location.split(',')
#                 width, height = dimensions.split('x')

#                 source_index = int(source_index, 0x10)
#                 dest_index = int(dest_index, 0x10)
#                 boundary_west = int(boundary_west, 0x10)
#                 boundary_north = int(boundary_north, 0x10)
#                 dest_x = int(dest_x, 0x10)
#                 dest_y = int(dest_y, 0x10)
#                 width = int(width)
#                 height = int(height)
#                 boundary_east = boundary_west + width - 1
#                 boundary_south = boundary_north + height - 1
#                 boundary = ((boundary_west, boundary_north),
#                             (boundary_east, boundary_south))
#                 MapMetaObject.get(source_index).add_or_replace_exit(
#                     boundary, dest_index, dest_x, dest_y, misc, exit_index)
#             elif line.startswith('!tile'):
#                 try:
#                     (command, tile_index, location, dimensions) = line.split()
#                 except ValueError:
#                     (command, tile_index, location) = line.split()
#                     dimensions = '1x1'
#                 map_index, location = location.split(':')
#                 boundary_west, boundary_north = location.split(',')
#                 width, height = dimensions.split('x')
#                 assert tile_index != '+1'
#                 tile_index = int(tile_index, 0x10)
#                 map_index = int(map_index, 0x10)
#                 boundary_west = int(boundary_west, 0x10)
#                 boundary_north = int(boundary_north, 0x10)
#                 width = int(width)
#                 height = int(height)
#                 boundary_east = boundary_west + width
#                 boundary_south = boundary_north + height
#                 boundary = ((boundary_west, boundary_north),
#                             (boundary_east, boundary_south))
#                 MapMetaObject.get(map_index).add_or_replace_tile(
#                     boundary, tile_index)
#             else:
#                 raise Exception('Unknown event patch command: %s' % line)
#             continue

#         if line.startswith('EVENT'):
#             while '  ' in line:
#                 line = line.replace('  ', ' ')
#             if identifier is not None:
#                 assert identifier not in to_import
#                 to_import[identifier] = script_text
#             identifier = line.strip().split(' ')[-1]
#             script_text = ''
#         else:
#             script_text = '\n'.join([script_text, line])

#     assert identifier not in to_import
#     to_import[identifier] = script_text
#     for identifier, script_text in sorted(to_import.items()):
#         map_index, el_index, script_index = identifier.split('-')
#         map_index = int(map_index, 0x10)
#         script_index = (None if script_index == 'XX'
#                         else int(script_index, 0x10))
#         meo = MapEventObject.get(map_index)
#         el = meo.get_eventlist_by_index(el_index)
#         script = el.get_or_create_script_by_index(script_index)
#         script.import_script(
#             script_text, warn_double_import=warn_double_import)
