


from copy import deepcopy
from functools import cached_property
from pathlib import Path
import re
from string import ascii_letters, digits, punctuation
from typing import cast
from args import args
from config import PROJECT_PATH
from helpers.files import BackupFile, new_file
from .names import Names
from structures.todo.properties import class_cached_property
from structures.todo.script import TableObject, hexify
from tables.zones import ZoneObject
from logger import iris



names: Names = Names()


class EventList:
    script: "Script"
    scripts: list["Script"]

    def __init__(self, pointer: int, meo: "MapEventObject"):
        self.pointer = pointer
        self.meo = meo
        if self.pointer == self.meo.npc_pointer:
            self.script_pointers = [(None, self.pointer)]
            return

        with BackupFile(new_file) as backup, backup.open("rb+") as f:
            f.seek(pointer)
            self.script_pointers = []
            while True:
                index = ord(f.read(1))
                if index == 0xFF:
                    break
                script_pointer = int.from_bytes(f.read(2), byteorder='little')
                self.script_pointers.append(
                    (index, self.meo.eventlists_pointer + script_pointer))
            MapEventObject.deallocate((self.pointer, f.tell()))

    def __repr__(self):
        s = ''
        for script in self.scripts:
            s += '\n' + script.pretty_with_header + '\n'
        return s.strip()

    @cached_property
    def index(self):
        i = self.meo.event_lists.index(self)
        return 'XABCDEF'[i]

    @property
    def map_meta(self):
        return self.meo.map_meta

    @property
    def eventlists_pointer(self):
        return self.meo.eventlists_pointer

    @property
    def size_estimate(self):
        if self.index == 'X':
            return len(self.script.data)
        total = (len(self.scripts)*3) + 1
        for script in self.scripts:
            total += len(script.data)
        return total

    def get_script_by_index(self, index: int | None) -> "Script" | None:
        if self.index == 'X':
            assert index is None
            assert len(self.scripts) == 1
            return self.scripts[0]

        candidates = [s for s in self.scripts if s.index == index]
        if len(candidates) == 1:
            return candidates[0]
        return None

    def get_or_create_script_by_index(self, index: int | None) -> "Script":
        script = self.get_script_by_index(index)
        if script:
            return script

        script = Script(None, 0, self, index=index)
        self.scripts.append(script)
        return script

    def read_scripts(self):
        self.scripts: list[Script] = []
        all_pointers = sorted(MapEventObject.ALL_POINTERS) # type: ignore[reportArgumentType]
        all_pointers: list[int]
        for index, pointer_1 in sorted(self.script_pointers):
            pointer_2 = next(
                pointer
                for pointer in all_pointers
                if pointer > pointer_1
            )
            script = Script(
                pointer_1,
                pointer_2-pointer_1,
                self,
                index
            )
            script.deallocate()
            self.scripts.append(script)
        if args.debug:
            for script in self.scripts:
                if script.frozen:
                    continue
                script.data = script.compile()
                script.script = script.parse(script.data)
                script.import_script(script.pretty)
                assert script.validate_no_change()
                script.script = script.old_script

    def write(self):
        for script in self.scripts:
            assert script.event_list is self
            script.realign_addresses()
        with BackupFile(new_file) as backup, backup.open("rb+") as f:
            npc_loader = (self.index == 'X')
            if npc_loader:
                assert len(self.scripts) == 1
                script = self.scripts[0]
                data = script.compile(optimize=True)
                assert data[-1] == 0
                self.pointer = MapEventObject.allocate(
                    len(data), npc_loader=npc_loader)
                script.script_pointer = self.pointer
                script.data = script.compile(optimize=True)
                f.seek(script.script_pointer)
                f.write(script.data)
                assert f.tell() == self.pointer + len(data)
                return

            self.pointer = MapEventObject.allocate(
                (len(self.scripts)*3) + 1, near=self.meo.eventlists_pointer)
            f.seek(self.pointer)

            if not hasattr(self.meo, 'assigned_zero'):
                for i, script in enumerate(self.scripts):
                    if script.index == 0:
                        self.meo.assigned_zero = self.pointer + (i*3)

            for i, script in enumerate(self.scripts):
                data = script.compile(optimize=True, ignore_pointers=True)
                assert data[-1] == 0
                if data[0] == 0 and hasattr(self.meo, 'assigned_zero'):
                    assert data == b'\x00'
                    assert hasattr(self.meo, 'assigned_zero')
                    if (args.debug and
                            self.meo.assigned_zero != self.pointer + (i*3)):
                        f.flush()
                        f.seek(self.meo.assigned_zero)
                        peek = f.read(1)
                        assert peek == b'\x00'
                    script.script_pointer = self.meo.assigned_zero
                else:
                    script.script_pointer = MapEventObject.allocate(
                        len(data), npc_loader=npc_loader,
                        find_best_fit_dry=True,
                        near=[self.meo.eventlists_pointer, self.pointer],
                        )
                    assert 0 <= script.script_pointer - self.meo.eventlists_pointer <= 0xffff
                    assert 0 <= script.script_pointer - self.pointer <= 0xffff
                    script.data = script.compile(optimize=True)
                    #assert len(script.data) == len(data)
                    MapEventObject.allocate(
                        len(script.data), npc_loader=npc_loader,
                        forced=script.script_pointer)
                    f.seek(script.script_pointer)
                    f.write(script.data)
                    assert b'\x00' in script.data
                    if not hasattr(self.meo, 'assigned_zero'):
                        zero_index = script.data.index(b'\x00')
                        self.meo.assigned_zero = (script.script_pointer + zero_index)
                script_pointer = script.script_pointer
                offset = script_pointer - self.meo.eventlists_pointer
                assert 0 <= offset <= 0xffff
                f.seek(self.pointer + (3*i))
                assert script.index is not None
                f.write(bytes([script.index]))
                f.write(offset.to_bytes(2, byteorder='little'))
            f.write(b'\xff')
            assert f.tell() == self.pointer + (3 * len(self.scripts)) + 1
            if args.debug and hasattr(self.meo, 'assigned_zero'):
                f.seek(self.meo.assigned_zero)
                peek = f.read(1)
                assert peek == b'\x00'

class Address:
    def __init__(self, address: int, is_local: bool):
        assert 0 <= address <= 0x7fff
        self.address = address
        self.old_address = address
        self.is_local = is_local
        if not is_local:
            raise NotImplementedError('Non-local address.')

    def __repr__(self):
        return f'{'@' if self.is_local else '&'}{self.address:X}'

    def __copy__(self):
        return self(self.address, self.is_local) # type: ignore


type TextType = tuple[str | int | None, bytes]
type SingleParam = int | Address | str | TextType | None
type ParamsType = list[SingleParam] | str
type ScriptType = list[
    tuple[
        int,  # Line number
        int,  # OP Code
        ParamsType,
    ]
]
class Script:
    INSTRUCTIONS_FILE = Path(PROJECT_PATH)/"info/event_instructions.txt"
    FULL_PARAMETERS: dict[int, list[str | int]] = {}
    COMMENTS = {}

    # Parse the instructions file.
    for line in INSTRUCTIONS_FILE.read_text().split('\n'):
        while '  ' in line:
            line = line.replace('  ', ' ')
        line = line.split(' ', 2)
        if len(line) == 2:
            opcode, num_parameters = line
            comment = None
        else:
            opcode, num_parameters, comment = line
        opcode = int(opcode, 0x10)
        temp = num_parameters.split(',')
        temp = [int(p) if p in digits else p for p in temp]
        temp = [p for p in temp if p != 0]
        FULL_PARAMETERS[opcode] = temp
        if comment:
            COMMENTS[opcode] = comment

    LINE_MATCHER = re.compile(r'^\s*([0-9a-fA-F]{1,4})\.', flags=re.MULTILINE)
    ADDRESS_MATCHER = re.compile(r'@([0-9A-Fa-f]+)[^0-9A-Fa-f]', flags=re.DOTALL)

    def __init__(
        self,
        script_pointer: int | None,
        data_length: int,
        event_list: EventList | None = None,
        index: int | None = None,
    ):
        self.event_list = event_list
        self.index = index
        self.frozen = False

        if script_pointer is not None:
            with BackupFile(new_file) as backup, backup.open("rb") as f:
                f.seek(script_pointer)
                self.data = f.read(data_length)
        else:
            self.data = b""

        self.old_script_pointer = script_pointer
        self.old_base_pointer = self.base_pointer
        self.old_data = self.data
        if script_pointer is None:
            self.script_pointer = self.base_pointer
        else:
            self.script_pointer = script_pointer

        self.script = self.parse(self.data)
        self.old_script = deepcopy(self.script)
        self.old_pretty = self.pretty

    def __repr__(self):
        return self.pretty_with_header

    @property
    def eventlists_pointer(self):
        assert self.event_list
        return self.event_list.eventlists_pointer

    @property
    def map_meta(self):
        assert self.event_list
        return self.event_list.map_meta

    @property
    def is_npc_load_event(self):
        return self.index is None

    @property
    def base_pointer(self):
        if not self.is_npc_load_event:
            return self.eventlists_pointer
        else:
            return self.script_pointer & 0xff8000

    @property
    def pretty(self):
        pretty = self.prettify_script(self.script)
        address_matches = self.ADDRESS_MATCHER.findall(pretty)
        address_matches = sorted(set(
            int(match, 0x10)
            for match in address_matches
        ))
        done_labels = set()
        for offset in reversed(address_matches):
            if offset in done_labels:
                continue
            done_labels.add(offset)
            line_code = f'{offset:0>4X}. '
            try:
                index = pretty.index(line_code)
                replacement = f'# LABEL @{offset:X} ${self.script_pointer+offset:x}\n{line_code}'
                pretty = pretty.replace(line_code, replacement)
            except ValueError:
                pretty = pretty.replace(f'@{offset:X}', f'@{offset:X}!')

        return pretty.rstrip()

    @property
    def header(self):
        header = f'EVENT {self.signature}  # ${self.event_list.pointer:x}:{self.script_pointer:x}'
        return header

    @property
    def signature(self):
        if self.index is not None:
            si = '{self.index:0>2X}'
        else:
            si = 'XX'
        return f'{self.event_list.meo.index:0>2X}-{self.event_list.index}-{si}'

    @property
    def pretty_with_header(self):
        s = f'{self.header}\n{self.pretty}'
        s = s.replace('\n', '\n  ')
        return s.strip()

    @property
    def opcount(self):
        return Counter(
            [opcode for line_number, opcode, parameters in self.script])

    @cached_property
    def pre_data(self):
        pointer = self.script_pointer - 0x1000
        assert pointer >= 0
        with BackupFile(new_file) as backup, backup.open("rb") as f:
            f.seek(pointer)
            return f.read(0x1000)

    @classmethod
    def get_pretty_variable(cls, variable: int):
        var_name = f'Variable {variable:0>2X} (${variable + 0x079e:0>4x})'
        return var_name

    @classmethod
    def get_pretty_flag(cls, flag: int):
        address = 0x77e + (flag // 8)
        bit = 1 << (flag % 8)
        fname = f'Flag {flag:0>2X} (${address:0>4x}:{bit:0>2x})'
        return fname

    @staticmethod
    def shift_line_numbers(script_text: str, offset: int):
        new_text: list[str] = []
        for line in script_text.split('\n'):
            if '. ' in line and ('(' in line or ':' in line):
                line = line.lstrip()
                if '.' in line[:5] and line[0] != '#':
                    while line[4] != '.':
                        line = '0' + line
            new_text.append(line)
        script_text = '\n'.join(new_text)

        lines = Script.LINE_MATCHER.findall(script_text)
        for line in lines:
            value = int(line, 0x10)
            assert value < offset
            line = f'{value:0>4X}'
            replacement = f'{value+offset:0>4X}'
            script_text = script_text.replace(f'{line.upper()}. ', f'{replacement}. ')
            script_text = script_text.replace(f'{line.upper()}. ', f'{replacement}. ')
        lines = Script.ADDRESS_MATCHER.findall(script_text)
        lines = sorted(lines, key=lambda i: -int(line, 0x10)) # type: ignore[reportUnknownArgumentType]
        for line in lines:
            value = int(line, 0x10)
            assert value < offset
            replacement = f'{value+offset:X}'
            script_text = re.sub(fr'@{line}(\W)', fr'@{replacement}\1', script_text)
        return script_text

    def prettify_script(self, script: "Script") -> str:
        if not hasattr(MapEventObject, '_script_cache'):
            MapEventObject.script_cache = {}
        key = str(script)
        if key in MapEventObject.script_cache:
            return MapEventObject.script_cache[key]

        pretty = ''
        for line_number, opcode, parameters in script:
            line_number = cast(int, line_number)
            opcode = cast(int, opcode)
            parameters = cast(str, parameters)

            line = ''
            if self.FULL_PARAMETERS[opcode] == ['text']:
                text = MapEventObject.prettify_text(parameters)
                text_lines = text.split('\n')
                justifiers = [f'{opcode:0>2X}:']
                justifiers += ([''] * len(text_lines)) # type: ignore[reportUnknownArgumentType]
                for left, right in zip(justifiers, text_lines): # type: ignore[reportUnknownArgumentType]
                    line += f'{left:3} {right}\n'
                line = line.rstrip()
                line = line.replace('\n', '\n      ')
                line = f'{line_number:0>4X}. {line}'
            else:
                if len(parameters) > 16:
                    param_str = hexify(parameters[:16])
                    param_str += f'... [{parameters} bytes]'
                else:
                    params = []
                    parameter_types = list(
                        self.FULL_PARAMETERS[opcode])
                    if ('variable' in parameter_types and parameters[0] in {0xc0, 0xc2}): # type: ignore[reportUnknownArgumentType]
                        assert len(parameter_types) == 1
                        parameter_types += [2, 2]
                    while len(parameter_types) < len(parameters):
                        if isinstance(parameter_types[-1], int):
                            assert 'variable' in parameter_types
                            parameter_types.append(1)
                        else:
                            parameter_types.append(parameter_types[-1])

                    for pt, p in zip(parameter_types, parameters):
                        if isinstance(p, int):
                            if pt in ['pointers', 'variable']:
                                pt = 1
                            assert isinstance(pt, int)
                            assert pt > 0
                            s = f'{p:0>{pt * 2}X}'
                        else:
                            assert isinstance(p, Address)
                            s = str(p)
                        params.append(s)
                    param_str = '-'.join(params) # type: ignore[reportUnknownArgumentType]
                line = f'{opcode:0>2X}({param_str})'

                # determine custom comments
                if opcode in self.COMMENTS:
                    comment = self.COMMENTS[opcode]
                else:
                    comment = ''

                if opcode in [0x68, 0x7b]:
                    npc_index, sprite_index = parameters
                    if self.map_meta:
                        position = self.map_meta.get_npc_position_by_index(npc_index-0x4f)
                    else:
                        position = None
                    name = names.sprites[sprite_index]
                    if position:
                        x, y = position.x, position.y
                        x = f'{x:0>2x}'
                        y = f'{y:0>2x}'
                    else:
                        x, y = '??', '??'
                    comment += f' ({x},{y}) {npc_index:0>2x}: {sprite_index:0>2x} {name}'
                    comment += '\n'
                elif opcode == 0x53:
                    (formation_index,) = parameters
                    f = BossFormationObject.get(formation_index)
                    comment = f'{comment} ({f.name})'
                elif opcode in {0x20, 0x21}:
                    item_index, quantity = parameters
                    item_index |= (0x100 * (opcode-0x20))
                    item = ItemObject.get(item_index)
                    comment = f'{comment} ({item.name} x{quantity})'
                elif opcode == 0x23:
                    character_index, spell_index = parameters
                    character = CharacterObject.get(character_index)
                    spell = SpellObject.get(spell_index)
                    comment = f'{comment} ({character.name}: {spell.name})'
                elif opcode == 0x16:
                    event = f'[{parameters[0]:0>2X}-B-{parameters[1]:0>2X}] ({parameters[2]:0>2X})'
                    comment = f'{comment} {event}'
                elif opcode == 0x35:
                    assert parameters[0] >= 0x10
                    xnpc = RoamingNPCObject.get(parameters[0] - 0x10)
                    npc_signature = f'({parameters[0]:0>2X} {xnpc.sprite_name})'
                    loc_signature = f'(map {parameters[1]:0>2X}, NPC {parameters[2]:0>2X})'
                    comment = f'Move roaming NPC {npc_signature} to {loc_signature}'
                    comment += f' [{parameters[1]:0>2X}-C-{parameters[0]:0>2X}]'
                    roaming_comment = f'[{self.signature}] {comment}'
                    MapEventObject.roaming_comments.add(roaming_comment)
                elif opcode == 0x8C:
                    a = f'Load animation frame {parameters[1]:0>2X}-{parameters[2]:0>2X}'
                    b = f'for sprite {parameters[0]:0>2X}'
                    comment = f'{a} {b}'
                elif opcode == 0x14:
                    assert parameters[-3] in {0x20, 0x30}
                    assert isinstance(parameters[-2], Address)
                    assert parameters[-1] == 0xFF
                    conditions: list[int] = parameters[:-3]
                    s = 'If'
                    while conditions:
                        c = conditions.pop(0)
                        if c == 0xf0:
                            s += ' NPC ???'
                            conditions.pop(0)
                            conditions.pop(0)
                        elif c == 0xf8:
                            npc_index = conditions.pop(0)
                            assert npc_index >= 1
                            s += f' NPC {npc_index-1:0>2X} ???'
                            conditions.pop(0)
                        elif c in {0xc0, 0xc2}:
                            item_index = conditions.pop(0)
                            item_name = ItemObject.get(item_index).name
                            quantity = conditions.pop(0)
                            if c == 0xc0:
                                s += f' exactly {item_name} x{quantity} owned'
                            elif c == 0xc2:
                                s += f' at least {item_name} x{quantity} owned'
                        elif c in {0x10, 0x12}:
                            variable = conditions.pop(0)
                            value = conditions.pop(0)
                            var_name = self.get_pretty_variable(variable)
                            if c == 0x10:
                                s += f' {var_name} == {value}'
                            elif c == 0x12:
                                s += f' {var_name} >= {value}'
                        else:
                            assert c in {0x00, 0x40, 0x80,
                                            0x01, 0x41, 0x81}
                            if c & 0x40:
                                s += ' OR'
                            elif c & 0x80:
                                s += ' AND'
                            flag = conditions.pop(0)
                            s += ' ' + self.get_pretty_flag(flag)
                            if c & 1:
                                s += ' NOT'
                            s += ' set'
                    if parameters[-3] == 0x30:
                        s += f" then DON'T jump to {parameters[-2]}"
                    elif parameters[-3] == 0x20:
                        s += f" then jump to {parameters[-2]}"
                    comment = s.strip()
                    assert '  ' not in comment

                if comment.endswith('Flag'):
                    flag = parameters[0]
                    comment = comment.replace('Flag', self.get_pretty_flag(flag))

                if comment.endswith('Variable'):
                    variable = parameters[0]
                    comment = comment.replace('Variable', self.get_pretty_variable(variable))

                if comment.strip():
                    line = f'{line_number:0>4X}. {line:30} # {comment}'
                else:
                    line = f'{line_number:0>4X}. {line}'
            pretty += line.rstrip() + '\n'

        MapEventObject.script_cache[key] = pretty.rstrip()
        return self.prettify_script(script)

    def make_pointer(self, data: bytes):
        assert len(data) == 2
        offset = int.from_bytes(data, byteorder='little')
        pointer = self.base_pointer + offset
        is_local_pointer = (self.script_pointer <= pointer < self.script_pointer + len(self.data))
        if is_local_pointer:
            script_offset = self.script_pointer - self.base_pointer
            return Address(offset-script_offset, is_local_pointer)
        else:
            return Address(pointer, is_local_pointer)

    def parse_text(self, opcode: int, data: bytes, full_data: bytes | None=None):
        if full_data is None:
            full_data = self.data

        text: list[TextType] = []
        if opcode == 0x13:
            npc_index, data = data[:1], data[1:]
            text.append(('NPC', npc_index))
        elif opcode in {0x6d, 0x6e}:
            position, data = data[:2], data[2:]
            text.append(('POSITION', position))
        elif opcode == 0x9e:
            unknown, data = data[:1], data[1:]
            text.append(('POSITION', unknown))
        text.append((None, b''))

        while True:
            try:
                text_code, data = data[0], data[1:]
            except IndexError:
                break

            if text_code in MapEventObject.TEXT_TERMINATORS:
                text.append((text_code, b''))
                break
            elif text_code == 0xa:
                n = MapEventObject.TEXT_PARAMETERS[text_code]
                text_parameters, data = data[:n], data[n:]
                value = int.from_bytes(text_parameters, byteorder='little')
                length = (value >> 12) + 2
                pointer = (value & 0xfff) + 2
                consumed_data = full_data[:-len(data)]
                buffer_data = self.pre_data + consumed_data
                index = len(buffer_data) - pointer
                assert index >= 0
                repeat_text = buffer_data[index:index+length]
                assert len(repeat_text) == length
                text.append((None, repeat_text))

            elif text_code in MapEventObject.TEXT_PARAMETERS:
                n = MapEventObject.TEXT_PARAMETERS[text_code]
                text_parameters, data = data[:n], data[n:]
                assert len(text_parameters) == n
                text.append((text_code, text_parameters))
            else:
                if text[-1][0] is not None:
                    text.append((None, b''))
                a, b = text.pop()
                assert a is None
                b += bytes([text_code])
                text.append((a, b))

        text = [(a, b) for (a, b) in text if b or (a is not None)]
        for a, b in zip(text, text[1:]):
            if a is None: # type: ignore[reportUnnecessaryComparison]
                assert b is not None

        return text, data

    @classmethod
    def trim_script(cls, script: list[ScriptType]) -> list[ScriptType]:
        for i in range(len(script)-1, -1, -1):
            _, opcode, parameters = script[i]
            if opcode == 0:
                assert not parameters
                script = script[:i+1]
                break
            elif 'text' in cls.FULL_PARAMETERS[opcode]:
                #self.CHARACTER_MAP[parameters[-1][-1]] == '<END EVENT>'
                char_code = parameters[-1][0]
                if MapEventObject.CHARACTER_MAP[char_code] == '<END EVENT>':
                    break
        else:
            raise AssertionError('Script does not terminate.')
        return script


    def parse(self, data: bytes) -> list[ScriptType]:
        if self.frozen:
            return self.old_script

        full_data = data
        script: list[ScriptType] = []
        try:
            while data:
                consumed = len(full_data) - len(data)
                opcode, data = data[0], data[1:]
                assert opcode in self.FULL_PARAMETERS
                parameter_types = self.FULL_PARAMETERS[opcode]
                parameters: list[int | TextType | Address] = []
                for pt in parameter_types:
                    assert pt != 0
                    if pt == 'text':
                        text, data = self.parse_text(opcode, data)
                        parameters.extend(text)
                    elif pt == 'pointers':
                        num_pointers, data = data[0], data[1:]
                        parameters.append(num_pointers)
                        for _ in range(num_pointers):
                            pointer = self.make_pointer(data[:2])
                            data = data[2:]
                            parameters.append(pointer)
                    elif pt == 'variable':
                        assert opcode == 0x14
                        while True:
                            c, data = data[0], data[1:]
                            parameters.append(c)
                            if c == 0xff:
                                break
                            elif c & 0xf0 == 0xf0:
                                assert len(parameters) == 1
                                assert c in {0xf0, 0xf8}
                                # 0xf0 Monster on button
                                # 0xf8 if NPC state
                                parameters.append(data[0])
                                parameters.append(data[1])
                                data = data[2:]
                            elif c & 0xf0 == 0xc0:
                                # ???
                                assert len(parameters) == 1
                                assert c in {0xc0, 0xc2}
                                # 0xc0 Check item possessed exactly number
                                # 0xc2 Check item possessed GTE
                                item_index, data = data[:2], data[2:]
                                item_number, data = data[:2], data[2:]
                                item_index = int.from_bytes(
                                    item_index, byteorder='little')
                                item_number = int.from_bytes(
                                    item_number, byteorder='little')
                                parameters.append(item_index)
                                parameters.append(item_number)
                            elif c & 0xf0 == 0x10:
                                assert len(parameters) == 1
                                assert c in {0x10, 0x12}
                                # 0x10 Equals
                                # 0x12 GTE
                                parameters.append(data[0])
                                parameters.append(data[1])
                                data = data[2:]
                            elif c & 0xe0 == 0x20:
                                assert c in {0x20, 0x30}
                                # 0x20 Branch if True
                                # 0x30 Branch if False
                                pointer = self.make_pointer(data[:2])
                                data = data[2:]
                                parameters.append(pointer)
                            else:
                                assert c in {0x00, 0x01,
                                                0x40, 0x41,
                                                0x80, 0x81}
                                # 0x01 NOT
                                # 0x40 OR
                                # 0x80 AND
                                flag, data = data[0], data[1:]
                                parameters.append(flag)
                    elif pt == 'addr':
                        pointer = self.make_pointer(data[:2])
                        data = data[2:]
                        parameters.append(pointer)
                    else:
                        assert isinstance(pt, int)
                        assert pt > 0
                        assert len(data) >= pt
                        parameter, data = data[:pt], data[pt:]
                        parameter = int.from_bytes(parameter, byteorder='little')
                        parameters.append(parameter)
                if not script:
                    assert consumed == 0
                else:
                    assert consumed > 0
                script.append((consumed, opcode, parameters))
                if script == [(0, 0, [])]:
                    break
        except AssertionError:
            print(f'WARNING: Script {self.script_pointer:x}.')
            try:
                script = self.trim_script(script)
            except AssertionError:
                iris.warning(f'WARNING: Script {self.script_pointer:x} does not terminate.')
                script.append((len(full_data), 0, []))
        return script

    def import_script(self, text: str, warn_double_import: bool=True):
        warn_double_import = warn_double_import or args.debug
        assert not self.frozen
        if (warn_double_import and hasattr(self, '_imported') and self._imported):
            iris.warning(f'WARNING: Script {self.script_pointer:x} double imported.')
        self._imported = True

        line_matcher = re.compile(r'^ *([0-9A-Fa-f]+)\. (.*)$')
        lines = []
        prev_nr = None
        prev_line = None
        seen_line_numbers = set()
        for line in text.split('\n'):
            if '#' in line:
                line = line.split('#')[0]
            line = line.rstrip()
            if not line:
                continue
            match = line_matcher.match(line)
            if lines:
                prev_nr, prev_line = lines[-1]
            if match:
                line_number = int(match.group(1), 0x10)
                if prev_nr is not None and prev_nr >= line_number:
                    print(text)
                    raise Exception(f'SCRIPT {self.signature} {self.script_pointer:x} ERR: Lines out of order.')
                lines.append((line_number, match.group(2)))
                seen_line_numbers.add(line_number)
            else:
                lines[-1] = (prev_nr, '\n'.join([prev_line, line.strip()]))

        script = []
        try:
            for line_number, line in lines:
                assert line[2] in '(:'
                opcode = int(line[:2], 0x10)
                if line[2] == '(':
                    assert line[-1] == ')'
                    parameters = line[3:-1]
                    assert '(' not in parameters and ')' not in parameters
                    if parameters:
                        parameters = parameters.split('-')
                    else:
                        parameters = []
                    params = []
                    for p in parameters:
                        if p.startswith('@'):
                            offset = int(p[1:], 0x10)
                            is_local = offset in seen_line_numbers
                            assert is_local
                            addr = Address(address=offset,
                                                is_local=is_local)
                            params.append(addr)
                        else:
                            params.append(int(p, 0x10))
                    script.append((line_number, opcode, params))
                elif line[2] == ':':
                    linetext = line[3:].strip()
                    compress = opcode not in {0x6d, 0x6e}
                    newtext = MapEventObject.reverse_prettify_text(
                        linetext, compress=compress)
                    newscript = self.parse(bytes([opcode]) + newtext)
                    newpretty = self.prettify_script(newscript)
                    for linetextline in linetext.split('\n'):
                        assert linetextline in newpretty
                    assert len(newscript) == 1
                    new_number, new_op, new_params = newscript[0]
                    assert new_op == opcode
                    script.append((line_number, opcode, new_params))
        except Exception:
            raise Exception(f'SCRIPT {self.script_pointer:x} ERROR: {line_number}. {line}')

        self.script = script
        return script

    def compress(self, text: str, compress: bool=False):
        assert isinstance(text, bytes)
        old_buffer_length = len(self.compression_buffer)
        while text:
            maxlength = min(17, len(self.compression_buffer), len(text))
            for length in range(maxlength, 3, -1):
                if not compress:
                    continue
                substr = ''.join(chr(c) for c in text[:length])
                if any([ord(c) & 0x80 for c in substr]):
                    continue
                if substr not in self.compression_buffer:
                    continue
                subdata = self.compression_buffer[-0xffe:]
                subdata += '\x0a'
                if substr not in subdata:
                    continue
                pointer = len(subdata) - subdata.index(substr)
                length_field = (length - 2) << 12
                assert pointer <= 0xfff
                assert length_field & pointer == 0
                fields = length_field | pointer
                assert fields <= 0xffff
                # Compression is better? Need to test.
                self.compression_buffer += '\x0a'
                self.compression_buffer += chr(fields & 0xff)
                self.compression_buffer += chr(fields >> 8)
                text = text[length:]
                break
            else:
                self.compression_buffer += chr(ord(text[:1]))
                text = text[1:]
        return_length = len(self.compression_buffer) - old_buffer_length
        return_text = self.compression_buffer[-return_length:]
        assert len(return_text) == return_length
        return return_text

    def normalize_addresses(self):
        line_numbers = [ln for (ln, _, _) in self.script]
        offset = 0 - min(line_numbers)
        if offset == 0:
            return
        new_script = []
        for (line, op_code, parameters) in self.script:
            line += offset
            for param in parameters:
                if isinstance(param, Address):
                    param.address += offset
            new_script.append((line, op_code, parameters))
        self.script = new_script

    def realign_addresses(self):
        self.normalize_addresses()
        line_numbers = [ln for (ln, _, _) in self.script]
        new_script = []
        for i, (line_number, opcode, parameters) in enumerate(self.script):
            try:
                next_line_number = self.script[i+1][0]
            except IndexError:
                next_line_number = None
            addrs = [p for p in parameters if isinstance(p, Address)]
            for p in addrs:
                addr = p.address
                if addr not in line_numbers:
                    addr = min([ln for ln in line_numbers
                                if ln >= addr])
                    p.address = addr
            if len(addrs) == 1:
                addr = addrs[0]
                if addr.address == next_line_number:
                    continue
            new_script.append((line_number, opcode, parameters))
        self.script = new_script

    def compile(self, script: "Script" | None=None, optimize: bool=False, ignore_pointers: bool=False):
        if self.frozen:
            return self.old_data
        if script is None:
            script = self.script
        partial = {}
        previous_line_number = None
        self.compression_buffer = ''
        prevop = None
        assigned_zero = None
        zero_lines = set()
        for line_number, opcode, parameters in script:
            if opcode == 0:
                zero_lines.add(line_number)
                if assigned_zero is None:
                    assigned_zero = line_number
                elif prevop == 0 and optimize:
                    continue
            prevop = opcode
            if isinstance(line_number, str):
                line_number = int(line_number, 0x10)
            if previous_line_number is not None:
                assert line_number > previous_line_number
            previous_line_number = line_number

            parameter_types = list(self.FULL_PARAMETERS[opcode])
            if ('variable' in parameter_types
                    and parameters[0] in {0xc0, 0xc2}):
                assert len(parameter_types) == 1
                parameter_types += [2, 2]
            while len(parameter_types) < len(parameters):
                if isinstance(parameter_types[-1], int):
                    assert 'variable' in parameter_types
                    parameter_types.append(1)
                else:
                    parameter_types.append(parameter_types[-1])
            assert len(parameter_types) == len(parameters)

            line = []
            def append_data(to_append):
                if not isinstance(to_append, list):
                    to_append = [to_append]
                for ta in to_append:
                    if isinstance(ta, Address):
                        line.append(ta)
                        line.append(None)
                        self.compression_buffer += '💙💙'
                    elif isinstance(ta, int):
                        line.append(ta)
                        self.compression_buffer += chr(ta)
                    else:
                        raise Exception('Unexpected data type.')

            append_data(opcode)
            for pt, parameter in zip(parameter_types, parameters):
                if pt == 'text':
                    label, value = parameter
                    if isinstance(label, int):
                        append_data(label)
                        if value:
                            assert len(value) == 1
                            value = ord(value)
                            assert 0 <= value <= 0xff
                            append_data(value)
                    elif label is None:
                        assert isinstance(value, bytes)
                        #compress = opcode not in {0x6d, 0x6e}
                        compress = False
                        value = self.compress(value, compress=compress)
                        line += [ord(c) for c in value]
                    elif isinstance(value, bytes):
                        append_data([c for c in value])
                    else:
                        assert False
                        assert isinstance(value, int)
                        assert 0 <= value <= 0xFF
                        append_data(value)
                    continue

                if isinstance(parameter, Address):
                    append_data(parameter)
                elif pt in ['pointers', 'variable']:
                    append_data(parameter)
                else:
                    assert isinstance(pt, int)
                    value = parameter.to_bytes(pt, byteorder='little')
                    append_data([v for v in value])

            partial[line_number] = line

        address_conversions = {}
        running_length = 0
        for line_number in sorted(partial):
            assert running_length >= 0
            address_conversions[line_number] = running_length
            running_length += len(partial[line_number])

        new_data = b''
        for line_number, line in sorted(partial.items()):
            for value in line:
                if isinstance(value, Address) and not ignore_pointers:
                    assert value.is_local
                    if optimize and value.address in zero_lines:
                        value.address = assigned_zero
                    value.address = address_conversions[value.address]

            new_line = []
            for value in line:
                if value is None:
                    continue
                elif isinstance(value, Address):
                    script_offset = self.script_pointer - self.base_pointer
                    address = value.address + script_offset
                    if ignore_pointers:
                        address = 0
                    assert 0 <= address <= 0xffff
                    new_line.append(address & 0xFF)
                    new_line.append(address >> 8)
                else:
                    new_line.append(value)

            new_data += bytes(new_line)

        if not ignore_pointers:
            self.data = new_data
            self.script = self.parse(new_data)
        return new_data

    def validate_no_change(self):
        old = self.old_pretty
        new = self.pretty
        while '  ' in old:
            old = old.replace('  ', ' ')
        while '  ' in new:
            new = new.replace('  ', ' ')
        while ' \n' in old:
            old = old.replace(' \n', '\n')
        while ' \n' in new:
            new = new.replace(' \n', '\n')
        old = re.sub(r'\n..... ', '\n', old)
        new = re.sub(r'\n..... ', '\n', new)
        old = re.sub(r'@[^-)]+', '', old)
        new = re.sub(r'@[^-)]+', '', new)
        old = old.rstrip()
        new = new.rstrip()
        if args.debug and old != new:
            olds = old.split('\n')
            news = new.split('\n')
            for a, b in zip(olds, news):
                if a != b:
                    print()
                    print(a)
                    print(b)
                    import pdb
                    pdb.set_trace()
                else:
                    print(a)
        return old == new

    def deallocate(self):
        assert self.data == self.old_data
        MapEventObject.deallocate((self.script_pointer, self.script_pointer + len(self.data)))

    def optimize(self):
        addresses = [
            a.address
            for (l, o, p) in self.script for a in p
            if isinstance(a, Address)
        ]
        new_script = []
        prev_l, prev_o, prev_p = None, None, None
        for line_number, opcode, parameters in self.script:
            if (opcode == 0x69 and opcode == prev_o
                    and line_number not in addresses):
                new_script.remove((prev_l, prev_o, prev_p))
                line_number = prev_l
            new_script.append((line_number, opcode, parameters))
            if opcode == 0 and prev_o is None:
                break
            prev_l, prev_o, prev_p = line_number, opcode, parameters
        self.script = new_script

class MapEventObject(TableObject):
    every: list["MapEventObject"]
    map_name_pointer: int
    flag = 'w'
    flag_description = 'an open world seed'
    script_cache: dict[str, str]
    assigned_zero: int

    TEXT_PARAMETERS = {
        0x04: 1,
        0x05: 1,
        0x06: 1,
        0x0a: 2,
        }
    TEXT_TERMINATORS = {0x00, 0x01, 0x0b}

    ASCII_VISIBLE = ascii_letters + digits + punctuation + ' '
    CHARACTER_MAP = {
        0x00: '<END EVENT>',
        0x01: '<END MESSAGE>',
        0x03: '\n',
        0x04: '<PAUSE>',
        0x09: '$MAXIM$',
        0x0a: '<REPEAT>',
        0x0b: '<CHOICE>',
        0x0c: '?\n',
        0x0d: '!\n',
        0x0e: ',\n',
        0x0f: '.\n',
        }
    REVERSE_CHARACTER_MAP = {v: k for k, v in CHARACTER_MAP.items()}
    TAG_MATCHER = re.compile('<([^>]*) ([^> ]*)>')

    END_NPC_POINTER = 0x3ae4d
    END_EVENT_POINTER = 0x7289e
    free_space: list[tuple[int, int]] = []

    roaming_comments: set[str] = set()
    ZONES_FILENAME = 'zones.txt'
    zone_maps: dict[int, list[int]] = {}
    zone_names: dict[int, str] = {}
    reverse_zone_map: dict[int, int] = {}

    # Create a dictionary of zone maps and names.
    for k, v in ZoneObject.data.items():
        idx = k
        z_name = v['name']
        map_indices = v['indices']
        assert idx not in zone_maps
        assert idx not in zone_names
        zone_maps[idx] = map_indices
        zone_names[idx] = z_name
        for m in map_indices:
            assert m not in reverse_zone_map
            reverse_zone_map[m] = idx

    # MapEventObject methods
    def __repr__(self):
        s1 = f'# MAP {self.index:0>2X}-{self.pointer:0>5x} ({self.name})'
        check = f'[{self.index:0>2X}'
        roaming = [c for c in self.roaming_comments if check in c]
        out_roaming = [c for c in roaming if c.startswith(check)]
        in_roaming = [c for c in roaming if c not in out_roaming]
        s2, s3, s4, s5 = '', '', '', ''
        for c in sorted(in_roaming):
            s3 += '# ' + c + '\n'
        for c in sorted(out_roaming):
            s5 += '# ' + c + '\n'
        if self.map_meta.exits:
            s1 += '\n' + self.map_meta.pretty_exits
            s1 = s1.replace('\n', '\n# EXIT ') + '\n'
        if self.map_meta.tiles:
            pretty_tiles = self.map_meta.pretty_tiles
            for line in pretty_tiles.split('\n'):
                tile_index = int(line.split()[0], 0x10)
                signature = f'{self.index:0>2X}-D-{tile_index:0>2X}'
                s2 += f'\n{line} [{signature}]'
            s2 = s2.replace('\n', '\n# TILE ') + '\n'

        if self.map_meta.npc_positions:
            s4 += '\n' + self.map_meta.pretty_positions
            s4 = s4.replace('\n', '\n# NPC ') + '\n'
        assert self.event_lists[0].index == 'X'
        npc_preload_matcher = re.compile(r'.*([0-9a-fA-F]{2}): (.*)$')
        preload_npcs = {}
        for line in str(self.event_lists[0]).split('\n'):
            if not ('. 68(' in line or '. 7B(' in line.upper()):
                continue
            match = npc_preload_matcher.match(line)
            if not match:
                continue
            npc_index, sprite = match.groups()
            npc_index = f'{int(npc_index, 0x10) - 0x4f:0>2X}'
            if npc_index in preload_npcs and preload_npcs[npc_index] != sprite:
                preload_npcs[npc_index] = 'VARIOUS'
            else:
                if '. 7B(' in line.upper():
                    mfo = MapFormationsObject.get(self.index)
                    formation = mfo.formations[int(npc_index, 0x10)-1]
                    sprite = f'{sprite} ({formation})'
                preload_npcs[npc_index] = sprite
        for npc_index, sprite in sorted(preload_npcs.items()):
            check = 'NPC %s' % npc_index
            try:
                index = s4.index(check)
            except ValueError:
                continue
            eol = s4[index:].index('\n') + index
            s4 = s4[:eol] + ' PRELOAD %s' % sprite + s4[eol:]
            assert index > 0
        s = f'{s1.strip()}\n{s2.strip()}\n{s3.strip()}\n{s4.strip()}\n{s5.strip()}\n'

        for c in ChestObject.get_chests_by_map_index(self.index):
            s += f'# {c}\n'

        s = s.strip()
        while '\n\n' in s:
            s = s.replace('\n\n', '\n')
        if '\n' in s:
            s += '\n'
        for el in self.event_lists:
            elstr = str(el).rstrip()
            if not elstr:
                continue
            s += '\n' + elstr + '\n'
        matcher = re.compile(fr'\[{self.index:0>2X}-.-..\]')
        matches = matcher.findall(s)
        for match in matches:
            checkstr = 'EVENT %s' % match[1:-1]
            if checkstr not in s:
                s = s.replace(' %s' % match, '')
        s = s.replace('\n', '\n  ')
        while '\n\n\n' in s:
            s = s.replace('\n\n\n', '\n\n')

        return s.strip()

    @cached_property
    def name(self):
        pointer = self.base_pointer + self.map_name_pointer
        with BackupFile(new_file) as backup, backup.open() as f:
            f.seek(pointer)
            name = b''
            while True:
                c = f.read(1)
                if c == b'\x00':
                    break
                name += c
            name, _ = self.parse_name(data=name, repeat_pointer=0x38000)
            name = self.prettify_text(name, no_opcodes=True)
            return re.sub('<..>', '?', name)

    @class_cached_property
    def ALL_POINTERS(self) -> set[int]:
        all_pointers: set[int] = set()
        for meo in MapEventObject.every:
            for el in meo.event_lists:
                sps = {pointer for (_, pointer) in el.script_pointers}
                all_pointers |= sps
                all_pointers.add(el.pointer)
            all_pointers.add(meo.eventlists_pointer)
            assert meo.npc_pointer in all_pointers
        all_pointers.add(self.END_EVENT_POINTER)
        all_pointers.add(self.END_NPC_POINTER)
        return all_pointers

    @class_cached_property
    def MIN_EVENT_LIST(self):
        return min(meo.eventlists_pointer for meo in MapEventObject.every)

    @property
    def map_meta(self):
        from .map_meta import MapMetaObject
        return MapMetaObject.get(self.index)

    @cached_property
    def base_pointer(self):
        assert self.pointer & 0xff8000 == 0x38000
        return self.pointer & 0xff8000

    @property
    def eventlists_pointer(self):
        pointer = (self.eventlist_highbyte << 15) | self.eventlist_lowbytes
        return self.base_pointer + pointer

    def set_eventlists_pointer(self, pointer: int):
        temp = pointer - self.base_pointer
        self.eventlist_highbyte = temp >> 15
        self.eventlist_lowbytes = temp & 0x7fff
        assert self.eventlists_pointer == pointer

    @property
    def npc_pointer(self):
        pointer = (self.npc_highbyte << 15) | self.npc_lowbytes
        return self.base_pointer + pointer

    def set_npc_pointer(self, pointer: int):
        temp = pointer - self.base_pointer
        self.npc_highbyte = temp >> 15
        self.npc_lowbytes = temp & 0x7fff
        assert self.npc_pointer == pointer

    def get_eventlist_by_index(self, index: int):
        candidates = [el for el in self.event_lists if el.index == index]
        assert len(candidates) == 1
        return candidates[0]

    @staticmethod
    def get_script_by_signature(signature: str) -> Script | None:
        meo_index, el_index, script_index = signature.split('-')
        meo = MapEventObject.get(int(meo_index, 0x10))
        el = meo.get_eventlist_by_index(el_index)
        if script_index == 'XX':
            assert el.index == 'X'
            script = el.get_script_by_index(None)
        else:
            script = el.get_script_by_index(int(script_index, 0x10))
        return script

    @property
    def event_pointers(self):
        listed_event_pointers = [
            p
            for (pointer, elist) in self.event_lists
            for (i, p) in elist
        ]
        return listed_event_pointers

    @property
    def zone_name(self):
        return self.zone_names[self.zone_index]

    @property
    def zone_index(self):
        if self.index in self.reverse_zone_map:
            return self.reverse_zone_map[self.index]
        return None

    def get_zone_enemies(self, old: bool=True):
        sprite_formation_matcher = re.compile(r'#.*PRELOAD (..) .* \(FORMATION (..):')
        result = []
        for meo in self.neighbors:
            if old:
                s = meo.old_pretty
            else:
                s = str(meo)
            sprite_formations = sprite_formation_matcher.findall(s)
            for sprite, formation in sprite_formations:
                sprite = int(sprite, 0x10)
                formation = FormationObject.get(int(formation, 0x10))
                result.append((sprite, formation))
        return result

    @property
    def neighbors(self):
        if self.zone_index is None:
            return [self]
        return [MapEventObject.get(m)
                for m in sorted(self.zone_maps[self.zone_index])]

    def change_escapability(self, make_escapable: bool=True):
        NO_ESCAPE_BIT = 0x08
        script = self.get_script_by_signature(f'{self.index:0>2X}-X-XX')
        script.optimize()
        new_script = []
        for (line, op_code, pointer) in script.script:
            if op_code == 0x69:
                assert len(pointer) == 1
                value = pointer[0]
                no_change = bool(value & NO_ESCAPE_BIT) != make_escapable
                if not no_change:
                    value ^= NO_ESCAPE_BIT
                pointer = [value]
            new_script.append((line, op_code, pointer))
        script.script = new_script

    @classmethod
    def deallocate(cls, to_deallocate: tuple[int, int]):
        if isinstance(to_deallocate, tuple):
            to_deallocate = {to_deallocate}
        temp = sorted(set(cls.free_space) | to_deallocate)
        while True:
            temp = sorted(temp)
            for ((a1, b1), (a2, b2)) in zip(temp, temp[1:]):
                assert a1 <= a2
                assert a1 < b1
                assert a2 < b2
                if a1 <= a2 <= b1:
                    temp.remove((a1, b1))
                    temp.remove((a2, b2))
                    temp.append((min(a1, a2), max(b1, b2)))
                    break
            else:
                break

        cls.free_space = sorted(temp)

    @classmethod
    def separate_free_space_banks(cls):
        free_space = []
        for (a, b) in cls.free_space:
            assert b > a
            while (b & 0xFF8000) > (a & 0xFF8000):
                new_a = (a & 0xFF8000) + 0x8000
                free_space.append((a, new_a))
                a = new_a
            free_space.append((a, b))
        cls.free_space = free_space

    @classmethod
    def allocate(self, length: int, npc_loader: bool=False, near=None,
                 find_best_fit_dry: bool=False, forced=None):
        if npc_loader:
            candidates = [
                (a, b)
                for (a, b) in self.free_space
                if a < self.MIN_EVENT_LIST and (b-a) >= length
            ]
        else:
            candidates = [
                (a, b)
                for (a, b) in self.free_space
                if a >= self.MIN_EVENT_LIST and (b-a) >= length
            ]

        if forced is not None:
            candidates = [(a, b) for (a, b) in candidates if a == forced]
        if near is not None:
            if not isinstance(near, list):
                near = [near]
            for n in near:
                candidates = [
                    (a, b)
                    for (a, b) in candidates
                    if 0 <= a - n <= 0x7fff
                ]

        candidates = [
            (a, b)
            for (a, b) in candidates
            if a & 0xFF8000 == (a+length-1) & 0xFF8000
        ]

        if not candidates:
            raise Exception('Not enough free space.')

        if find_best_fit_dry:
            candidates = sorted(candidates, key=lambda x: (x[1]-x[0], x))
            a, b = candidates.pop(0)
            return a

        a, b = candidates.pop(0)
        remaining = (a+length, b)
        assert remaining[0] <= remaining[1]
        self.free_space.remove((a, b))
        if remaining[0] < remaining[1]:
            self.free_space.append(remaining)
        self.free_space = sorted(self.free_space)
        assert a & 0xFF8000 == (a+length-1) & 0xFF8000
        return a

    @classmethod
    def parse_name(self, data: bytes, repeat_pointer: int):
        text = []
        text.append((None, b''))
        while True:
            try:
                textcode, data = data[0], data[1:]
            except IndexError:
                break
            if textcode in self.TEXT_TERMINATORS:
                text.append((textcode, b''))
                break
            elif textcode == 0xa:
                n = self.TEXT_PARAMETERS[textcode]
                text_parameters, data = data[:n], data[n:]
                value = int.from_bytes(text_parameters, byteorder='little')
                length = (value >> 12) + 2
                pointer = value & 0xfff
                p = repeat_pointer + pointer
                with BackupFile(new_file) as backup, backup.open("rb") as f:
                    f.seek(p)
                    repeat_text = f.read(length)
                    text.append((None, repeat_text))
            elif textcode in self.TEXT_PARAMETERS:
                n = self.TEXT_PARAMETERS[textcode]
                text_parameters, data = data[:n], data[n:]
                text.append((textcode, text_parameters))
            else:
                if text[-1][0] is not None:
                    text.append((None, b''))
                a, b = text.pop()
                assert a is None
                b += bytes([textcode])
                text.append((a, b))
        text = [(a, b) for (a, b) in text if b or (a is not None)]
        for a, b in zip(text, text[1:]):
            if a is None:
                assert b is not None
        return text, data

    @classmethod
    def prettify_text(cls, text_script: str, no_opcodes: bool=False):
        s = ''
        for opcode, parameters in text_script:
            if no_opcodes:
                opcode = None
            if opcode in {5, 6}:
                index = parameters[0]
                index += (0x100 * (opcode-5))
                word = WordObject.get(index).word
                s += word
            elif opcode in cls.TEXT_TERMINATORS:
                if opcode in cls.CHARACTER_MAP:
                    s += cls.CHARACTER_MAP[opcode]
                else:
                    s += '<END MESSAGE>'
            elif opcode == 'NPC':
                assert len(parameters) == 1
                s += f'<VOICE {parameters[0]:0>2X}>'
            elif opcode == 'POSITION':
                assert 1 <= len(parameters) <= 2
                s += f'<POSITION {hexify(parameters)}>'
            elif opcode == 'COMMENT':
                s += f'<{parameters}>'
            elif opcode is None:
                for c in parameters:
                    if c in cls.CHARACTER_MAP and not no_opcodes:
                        s += cls.CHARACTER_MAP[c]
                    elif c & 0x80:
                        index = c & 0x7F
                        try:
                            w = WordObject.get(index + 0x200)
                            s += w.word
                        except KeyError:
                            s += f'<{c:0>2X}>'
                    else:
                        if chr(c) in cls.ASCII_VISIBLE:
                            s += chr(c)
                        else:
                            s += f'<{c:0>2X}>'
            elif opcode in cls.CHARACTER_MAP:
                sub = cls.CHARACTER_MAP[opcode]
                assert sub[-1] == '>'
                if parameters:
                    sub = sub.rstrip('>')
                    sub = f'{sub} {hexify(parameters)}>'
                s += sub
            elif isinstance(opcode, str):
                s += f'<{opcode} {hexify(parameters)}>'
            else:
                raise Exception('Unhandled text opcode %x.' % opcode)
        return s

    @classmethod
    def reverse_prettify_text(self, message, compress=True):
        reverse_keys = sorted(self.REVERSE_CHARACTER_MAP,
                              key=lambda k: (-len(k), k))
        parameters = [message]
        while True:
            reset_flag = False
            for i, p in list(enumerate(parameters)):
                if not isinstance(p, str):
                    continue
                if len(p) == 2 and p[0] in '\x05\x06':
                    continue
                for k in reverse_keys:
                    if k in p:
                        p1, p2 = p.split(k, 1)
                        parameters = (parameters[:i] +
                                      [p1, self.REVERSE_CHARACTER_MAP[k], p2] +
                                      parameters[i+1:])
                        reset_flag = True
                        break
                if reset_flag:
                    break
                match = self.TAG_MATCHER.search(p)
                if match:
                    k = match.group(0)
                    values = [int(v, 0x10) for v in match.group(2).split('-')]
                    label = '<%s>' % match.group(1)
                    if label in self.REVERSE_CHARACTER_MAP:
                        values.insert(0, self.REVERSE_CHARACTER_MAP[label])
                    p1, p2 = p.split(k, 1)
                    parameters = (parameters[:i] + [p1] + values + [p2] +
                                  parameters[i+1:])
                    break
                if not compress:
                    continue
                new_p = WordObject.compress(p)
                assert isinstance(new_p, list)
                if len(new_p) == 1 and new_p[0] == p:
                    continue
                parameters = parameters[:i] + new_p + parameters[i+1:]
                break
            else:
                if not reset_flag:
                    break
        for p in parameters:
            if isinstance(p, str):
                if len(p) == 2 and p[0] in '\x05\x06':
                    continue
                assert '<' not in p and '>' not in p
        parameters = [
            param
            if isinstance(param, str) else chr(param)
            for param in parameters
            if param != ''
        ]
        result = bytes([ord(c) for c in ''.join(parameters)])
        return result

    def read_data(self, filename: str | None=None, pointer: int | None=None):
        super().read_data(filename, pointer)

        self.event_lists = [EventList(self.npc_pointer, self)]

        with BackupFile(new_file) as backup, backup.open('r+b') as f:
            f.seek(self.eventlists_pointer)
            self.unknown = int.from_bytes(f.read(2), byteorder='little')
            for i in range(6):
                f.seek(self.eventlists_pointer + 2 + (i*2))
                relative_pointer = int.from_bytes(f.read(2), byteorder='little')
                absolute_pointer = self.eventlists_pointer + relative_pointer
                el = EventList(absolute_pointer, self)
                self.event_lists.append(el)

        self.deallocate((self.eventlists_pointer, self.eventlists_pointer + 14))
        assert len(self.event_lists) == 7

    def preprocess(self):
        assert not hasattr(self, 'event_associations')
        for el in self.event_lists:
            el.read_scripts()
        self.old_pretty = str(self)

    @classmethod
    def full_cleanup(cls):
        cls.separate_free_space_banks()
        with BackupFile(new_file) as backup, backup.open("r+b") as f:
            for (a, b) in cls.free_space:
                f.seek(a)
                f.write(b'\x00' * (b-a))
            if args.debug:
                cls._cleanup_text = '\n'.join([str(meo) for meo in MapEventObject.every])
            super().full_cleanup()

    @classmethod
    def purge_orphans(cls):
        if not hasattr(MapEventObject, '_cleanup_text'):
            MapEventObject._cleanup_text = '\n'.join([str(meo) for meo in MapEventObject.every])
        for meo in MapEventObject.every:
            for el in meo.event_lists:
                for script in list(el.scripts):
                    if el.index == 'C':
                        find_sig = f'[{script.signature}]'
                        if find_sig not in MapEventObject._cleanup_text:
                            el.scripts.remove(script)

    def cleanup(self):
        for el in self.event_lists:
            for script in el.scripts:
                script.optimize()
            if el.index == 'X':
                continue
            for script in list(el.scripts):
                if (el.index in 'AD' and
                        {op_code for (_, op_code, _) in script.script} == {0}):
                    el.scripts.remove(script)
                    continue

                find_sig = '[{self.script_signature}]'
                if (args.debug and el.index in 'CD' and find_sig not in self._cleanup_text):
                    iris.warning(f'WARNING: Orphaned event {find_sig}.')

        s = str(self)
        for tile in list(self.map_meta.tiles):
            signature = f'EVENT {self.index:0>2X}-D-{tile.index:0>2X}'
            if signature not in s:
                self.map_meta.tiles.remove(tile)


    def write_data(self, filename: str | None=None, pointer: int | None=None, syncing: bool=False):
        with BackupFile(new_file) as backup, backup.open('r+b') as f:
            self.set_eventlists_pointer(self.allocate(14, npc_loader=False))
            f.seek(self.eventlists_pointer)
            f.write(self.unknown.to_bytes(2, byteorder='little'))

            empty_eventlist = None
            for (i, el) in enumerate(self.event_lists):
                if (el.index != 'X' and len(el.scripts) == 0
                        and empty_eventlist is not None):
                    el.pointer = empty_eventlist
                else:
                    el.write()
                    if el.index != 'X' and len(el.scripts) == 0:
                        empty_eventlist = el.pointer

                if el.index == 'X':
                    self.set_npc_pointer(el.pointer)
                    continue

                relative_pointer = el.pointer - self.eventlists_pointer
                f.seek(self.eventlists_pointer + (i * 2))
                f.write(relative_pointer.to_bytes(2, byteorder='little'))
            assert f.tell() == self.eventlists_pointer + 14
            super().write_data(filename, pointer)
