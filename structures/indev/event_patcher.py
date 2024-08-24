from structures.indev.events import Boundary, Destination, MapEvent, Tile, Exit, NPCPosition


def filter_line(line: str) -> str:
    if '#' in line:
        index = line.index('#')
        line = line[:index].rstrip()
    line = line.lstrip()
    return line


def clean_whitespace(line: str) -> str:
    while '  ' in line:
        line = line.replace('  ', ' ')
    return line


def parse_npc(line: str):
    (_command, npc_index, misc, location) = line.split()
    map_index, location = location.split(':')
    a, b = location.split(',')
    map_index = int(map_index, 0x10)
    if npc_index == '+1':
        npc_index = None
    else:
        npc_index = int(npc_index, 0x10)
    try:
        assert misc.startswith('(')
        assert misc.endswith(')')
    except Exception as e:
        raise Exception('Malformed "misc" field: %s' % line) from e
    misc = int(misc[1:-1], 0x10)
    (x, y, boundary_west, boundary_east, boundary_north,
        boundary_south) = None, None, None, None, None, None
    for axis, value_range in zip(('x', 'y'), (a, b)):
        assert '>' not in value_range
        if '<' in value_range:
            left, middle, right = value_range.split('<=')
            left = int(left, 0x10)
            middle = int(middle, 0x10)
            right = int(right, 0x10)
            assert left <= middle <= right
            if axis == 'x':
                boundary_west = left
                x = middle
                boundary_east = right
            else:
                assert axis == 'y'
                boundary_north = left
                y = middle
                boundary_south = right
        else:
            if axis == 'x':
                x = int(value_range, 0x10)
            else:
                assert axis == 'y'
                y = int(value_range, 0x10)
    assert x
    assert y
    assert boundary_west
    assert boundary_east
    assert boundary_north
    assert boundary_south
    map_event = MapEvent.from_index(map_index)
    map_event.set_npc(
        NPCPosition(
            npc_index or len(map_event.npc_positions),
            x,
            y,
            Boundary(
                boundary_west,
                boundary_north,
                boundary_east,
                boundary_south
            ),
            misc
        )
    )


def parse_exit(line: str):
    try:
        (_command, exit_index, misc, movement, dimensions) = line.split()
    except ValueError:
        (_command, exit_index, misc, movement) = line.split()
        dimensions = '1x1'

    if exit_index == '+1':
        exit_index = None
    else:
        exit_index = int(exit_index, 0x10)

    try:
        assert misc.startswith('(')
        assert misc.endswith(')')
    except Exception as e:
        raise Exception('Malformed "misc" field: %s' % line) from e
    misc = int(misc[1:-1], 0x10)

    source, destination = movement.split('->')
    source_index, source_location = source.split(':')
    dest_index, dest_location = destination.split(':')
    boundary_west, boundary_north = source_location.split(',')
    dest_x, dest_y = dest_location.split(',')
    width, height = dimensions.split('x')

    source_index = int(source_index, 0x10)
    dest_index = int(dest_index, 0x10)
    boundary_west = int(boundary_west, 0x10)
    boundary_north = int(boundary_north, 0x10)
    dest_x = int(dest_x, 0x10)
    dest_y = int(dest_y, 0x10)
    width = int(width)
    height = int(height)
    boundary_east = boundary_west + width - 1
    boundary_south = boundary_north + height - 1
    map_event = MapEvent.from_index(source_index)
    map_event.set_exit(
        Exit(
            exit_index or len(map_event.exits),
            Boundary(
                boundary_west,
                boundary_north,
                boundary_east,
                boundary_south
            ),
            misc,
            Destination(dest_x, dest_y, dest_index)
        )
    )

def parse_tile(line: str):
    try:
        (_command, tile_index, location, dimensions) = line.split()
    except ValueError:
        (_command, tile_index, location) = line.split()
        dimensions = '1x1'
    map_index, location = location.split(':')
    boundary_west, boundary_north = location.split(',')
    width, height = dimensions.split('x')
    assert tile_index != '+1'
    tile_index = int(tile_index, 0x10)
    map_index = int(map_index, 0x10)
    boundary_west = int(boundary_west, 0x10)
    boundary_north = int(boundary_north, 0x10)
    width = int(width)
    height = int(height)
    boundary_east = boundary_west + width
    boundary_south = boundary_north + height
    boundary = Boundary(boundary_west, boundary_north, boundary_east, boundary_south)
    MapEvent.from_index(map_index).set_tile(Tile(tile_index, boundary))


def parse_exclamation_mark(line: str):
    line = line.strip().lower()
    line = clean_whitespace(line)

    if line.startswith('!npc'):
        parse_npc(line)
    elif line.startswith('!exit'):
        parse_exit(line)
    elif line.startswith('!tile'):
        parse_tile(line)
    else:
        raise Exception('Unknown event patch command: %s' % line)
    return True

def parse_event(line: str, to_import: dict[str, str], identifier: str | None, script_text: str):
    line = clean_whitespace(line)
    if identifier is not None:
        assert identifier not in to_import
        to_import[identifier] = script_text
    identifier = line.strip().split(' ')[-1]
    script_text = ''
    return identifier, script_text


def apply_event_patches(script: str):
    # TODO: Have scripts as bytes (as the game does internally)
    to_import: dict[str, str] = {}
    identifier = None
    script_text = ""
    for line in script.split('\n'):
        line = filter_line(line)
        if not line:
            continue

        if line.startswith('!'):
            parse_exclamation_mark(line)
            continue
        if line.startswith('EVENT'):
            identifier, script_text = parse_event(line, to_import, identifier, script_text)
            continue
        script_text = '\n'.join([script_text, line])

    assert identifier
    assert identifier not in to_import
    to_import[identifier] = script_text

    for identifier, script_text in sorted(to_import.items()):
        map_index, el_index, script_index = identifier.split('-')
        map_event = MapEvent.from_index(int(map_index, 0x10))
        script_index = (None if script_index == 'XX' else int(script_index, 0x10))
        event_list = map_event.event_lists[el_index]
        script = event_list.get_or_create_script_by_index(script_index)
        script.import_script(script_text, warn_double_import=warn_double_import)
