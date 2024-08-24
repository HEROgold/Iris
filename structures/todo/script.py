"""
This file is from Absynonym's Terrorwave/Randomtools
The goal is to transform this to a script parser, so that we can use eventpatch_* files
for the Iris randomizer. The goal is to get a asm patch for asar, or hex data we can use.
"""

from abc import ABC
from collections import Counter
from copy import deepcopy
from functools import total_ordering
from io import BufferedRandom, BufferedReader
from math import ceil
from os import environ, path, stat
import random
import re
from string import digits, printable
from sys import stdout
from typing import Any, Callable, Self, Type
from _types.sentinels import MISSING
from args import args
from errors import FileEntryReadException
from .map_events import MapEventObject, MapMetaObject



tblpath = "tables"
head = __file__.rsplit("randomtools", 1)[0]
tblpath = path.join(head, tblpath)


MASTER_FILENAME = "master.txt"
TABLE_SPECS = {}
GLOBAL_OUTPUT = None
GLOBAL_TABLE = None
GLOBAL_LABEL = None
GRAND_OBJECT_DICT = {}
PATCH_FILENAMES = []
ALREADY_PATCHED = set()
OPTION_FILENAMES = []
NO_VERIFY_PATCHES = []
CMP_PATCH_FILENAMES = []
RANDOM_DEGREE = 0.25
DIFFICULTY = 1.0
SEED = None
PSX_FILE_MANAGER: "FileManager" = MISSING
OPEN_FILES: dict[str, BufferedRandom] = {}
ALL_FILES = set()
REMOVED_FILES = set()
MAX_OPEN_FILE_COUNT = 100
SANDBOX_PATH = "temp"


already_gotten: dict[tuple["TableObject", int, int], "TableObject"] = {}
def get_table_objects(cls: "TableObject", filename: str | None=None) -> "TableObject":
    pointer = cls.specs.pointer
    number = cls.specs.count
    grouped = cls.specs.grouped
    pointed = cls.specs.pointed
    delimit = cls.specs.delimit
    pointer_filename = cls.specs.pointer_filename
    identifier = (cls, pointer, number)
    if identifier in already_gotten:
        return already_gotten[identifier]

    if filename is None:
        filename = GLOBAL_OUTPUT
    objects = []

    def add_objects(
        n: int,
        group_index: int | None = 0,
        ptr: int | str | None = None,
        obj_filename: str | None = None,
    ):
        if obj_filename is None:
            obj_filename = filename
        if ptr is None:
            ptr = pointer
        accumulated_size = 0
        for _ in range(n):
            obj = cls(obj_filename, ptr, index=len(objects),
                          groupindex=group_index)
            objects.append(obj)
            ptr += obj.specs.total_size
            accumulated_size += obj.specs.total_size
        return accumulated_size

    def add_variable_object(p1, p2):
        size = p2 - p1
        obj = cls(filename, p1, index=len(objects),
                      groupindex=0, size=size)
        objects.append(obj)
        return size

    if pointer_filename is not None:
        for line in open(path.join(tblpath, pointer_filename)):
            line = line.strip()
            if not line or line[0] == '#':
                continue
            line = line.split()[0]
            if '@' in line:
                pointer, obj_filename = line.split('@')
                obj_filename = obj_filename.replace('/', path.sep)
                obj_filename = obj_filename.replace('\\', path.sep)
                obj_filename = path.join(SANDBOX_PATH, obj_filename)
            else:
                pointer = line
                obj_filename = None
            pointer = int(pointer, 0x10)
            add_objects(1, ptr=pointer, obj_filename=obj_filename)
    elif not grouped and not pointed and not delimit:
        add_objects(number)
    elif grouped:
        counter = 0
        while len(objects) < number:
            if cls.specs.groupednum is None:
                f = get_open_file(filename)
                f.seek(pointer)
                value = ord(f.read(1))
                pointer += 1
            else:
                value = cls.specs.groupednum
            pointer += add_objects(value, group_index=counter)
            counter += 1
    elif pointed and delimit:
        size = cls.specs.pointedsize
        counter = 0
        f = get_open_file(filename)
        while counter < number:
            f.seek(pointer)
            subpointer = read_multi(f, size) + cls.specs.pointedpointer
            while True:
                f.seek(subpointer)
                peek = ord(f.read(1))
                if peek == cls.specs.delimitval:
                    break
                obj = cls(filename, subpointer, index=len(objects),
                              groupindex=counter, size=None)
                objects.append(obj)
                subpointer += cls.specs.total_size
            pointer += size
            counter += 1
    elif pointed and cls.specs.total_size > 0:
        size = cls.specs.pointedsize
        counter = 0
        f = get_open_file(filename)
        while counter < number:
            f.seek(pointer)
            subpointer = read_multi(f, size) + cls.specs.pointedpointer
            f.seek(pointer + size)
            subpointer2 = read_multi(f, size) + cls.specs.pointedpointer
            groupcount = (subpointer2 - subpointer) // cls.specs.total_size
            if cls.specs.pointedpoint1:
                groupcount = 1
            add_objects(groupcount, group_index=counter, ptr=subpointer)
            pointer += size
            counter += 1
    elif pointed and cls.specs.total_size == 0:
        size = cls.specs.pointedsize
        counter = 0
        f = get_open_file(filename)
        while counter < number:
            f.seek(pointer + (size*counter))
            subpointer = read_multi(f, size) + cls.specs.pointedpointer
            f.seek(pointer + (size*counter) + size)
            subpointer2 = read_multi(f, size) + cls.specs.pointedpointer
            add_variable_object(subpointer, subpointer2)
            counter += 1
    elif delimit:
        f = get_open_file(filename)
        for counter in range(number):
            while True:
                f.seek(pointer)
                peek = ord(f.read(1))
                if peek == cls.specs.delimitval:
                    pointer += 1
                    break
                obj = cls(filename, pointer, index=len(objects),
                              groupindex=counter, size=None)
                objects.append(obj)
                pointer += obj.specs.total_size

    already_gotten[identifier] = objects

    return get_table_objects(cls, filename=filename)


def hexify(s: str | bytes):
    return "-".join("{0:0>2X}".format(c) for c in s)


def read_lines_nocomment(filename: str) -> list[str]:
    lines = []
    with open(filename) as f:
        for line in f:
            if "#" in line:
                line, _ = line.split("#", 1)
            line = line.rstrip()
            if not line:
                continue
            lines.append(line)
    return lines


def get_open_file(filepath: str, sandbox: bool = False) -> BufferedReader:
    filepath = filepath.replace("/", path.sep)
    filepath = filepath.replace("\\", path.sep)
    assert filepath not in REMOVED_FILES
    if sandbox and not filepath.startswith(SANDBOX_PATH):
        filepath = path.join(SANDBOX_PATH, filepath)
    if filepath in OPEN_FILES:
        f = OPEN_FILES[filepath]
        if not f.closed:
            return OPEN_FILES[filepath]

    if len(OPEN_FILES) >= MAX_OPEN_FILE_COUNT:
        for openfp in list(OPEN_FILES):
            close_file(openfp)

    if (
        filepath.startswith(SANDBOX_PATH)
        and path.sep in filepath
        and filepath not in ALL_FILES
    ):
        name = filepath[len(SANDBOX_PATH) :].lstrip(path.sep)
        PSX_FILE_MANAGER.export_file(name, filepath)

    f = open(filepath, "r+b")
    OPEN_FILES[filepath] = f
    ALL_FILES.add(filepath)
    return get_open_file(filepath)


def close_file(filepath: str):
    if filepath in OPEN_FILES:
        OPEN_FILES[filepath].close()
        del OPEN_FILES[filepath]


def get_outfile() -> str:
    return args.file + "out_file"


def remove_unused_file(filepath: str):
    close_file(filepath)
    REMOVED_FILES.add(filepath)
    if filepath in ALL_FILES:
        ALL_FILES.remove(filepath)


def create_psx_file_manager(outfile: str):
    global PSX_FILE_MANAGER
    PSX_FILE_MANAGER = FileManager(outfile, SANDBOX_PATH)


def get_psx_file_manager():
    global PSX_FILE_MANAGER
    assert PSX_FILE_MANAGER is not None
    return PSX_FILE_MANAGER


def reimport_psx_files():
    if not SANDBOX_PATH:
        return
    if not PSX_FILE_MANAGER:
        return
    last_import = -1
    for n, filepath in enumerate(sorted(ALL_FILES)):
        if filepath.startswith(SANDBOX_PATH):
            count = int(round(9 * n / len(ALL_FILES)))
            if count > last_import:
                if count == 0:
                    print("Re-importing files...")
                last_import = count
                stdout.write("%s " % (10 - count))
                stdout.flush()
            name = filepath[len(SANDBOX_PATH) :].lstrip(path.sep)
            close_file(filepath)  # do before importing to flush the file
            PSX_FILE_MANAGER.import_file(name, filepath)
    stdout.write("\n")
    PSX_FILE_MANAGER.finish()


def set_global_label(label):
    global GLOBAL_LABEL
    GLOBAL_LABEL = label


def get_global_label():
    global GLOBAL_LABEL
    return GLOBAL_LABEL


def set_global_output_filename(filename):
    global GLOBAL_OUTPUT
    GLOBAL_OUTPUT = filename


def set_global_table_filename(filename):
    global GLOBAL_TABLE
    GLOBAL_TABLE = filename


def get_seed():
    global SEED
    return SEED


def set_seed(seed):
    global SEED
    SEED = seed


def determine_global_table(outfile, interactive=True, allow_conversions=True):
    global GLOBAL_LABEL
    if GLOBAL_LABEL is not None:
        return GLOBAL_LABEL

    force_conversion = False
    tablefiles, labelfiles, conversions = {}, {}, {}
    for line in open(path.join(tblpath, MASTER_FILENAME)):
        line = line.strip()
        if not line or line[0] == "#":
            continue
        while "  " in line:
            line = line.replace("  ", " ")
        try:
            label, h2, tablefile = line.split()
            tablefiles[h2] = (label, tablefile)
            labelfiles[label] = tablefile
        except ValueError:
            conversion, ips_filename = line.split(" ")
            assert "->" in conversion
            convert_from, convert_to = conversion.split("->")
            if convert_from.startswith("!"):
                convert_from = convert_from.lstrip("!")
                force_conversion = True
            conversions[convert_from] = (convert_to, ips_filename)

    h = md5hash(outfile)
    if h in tablefiles:
        label, filename = tablefiles[h]
    elif interactive:
        print("Unrecognized rom file: %s" % h)
        for i, label in enumerate(sorted(labelfiles)):
            print("%s. %s" % ((i + 1), label))
        if len(labelfiles) > 1:
            selection = int(input("Choose 1-%s: " % len(labelfiles)))
            label = sorted(labelfiles.keys())[selection - 1]
            filename = labelfiles[label]
        else:
            input("Using this rom information. Okay? ")
            label = sorted(labelfiles.keys())[0]
            filename = labelfiles[label]
    else:
        return None

    if allow_conversions and label in conversions:
        convert_to, ips_filename = conversions[label]
        convert = True
        if interactive and not force_conversion:
            x = input("Automatically convert from {0} to {1}? (y/n) ")
            if x and x[0].lower() == "n":
                convert = False
        if convert:
            ips_patch(outfile, path.join(tblpath, ips_filename))
            label = convert_to
            h = md5hash(outfile)
            assert h in tablefiles and tablefiles[h][0] == label
            filename = labelfiles[label]

    set_global_label(label)
    set_global_table_filename(filename)
    return GLOBAL_LABEL


def patch_filename_to_bytecode(patchfilename):
    patch = {}
    validation = {}
    definitions = {}
    labels = {}
    next_address = None
    filename = None
    read_into = patch
    f = open(patchfilename)
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
            try:
                _, name, address = line.split(" ")
                labels[name] = (address, filename)
            except ValueError:
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
            address = next_address
        else:
            if "@" in address:
                address, filename = address.split("@")
                filename = filename.replace("/", path.sep)
                filename = filename.replace("\\", path.sep)
            address = int(address, 0x10)
        code = code.strip()
        while "  " in code:
            code = code.replace("  ", " ")

        if (address, filename) in read_into:
            raise Exception("Multiple %x patches used." % address)
        if code:
            read_into[(address, filename)] = code
        for name in labels:
            if labels[name] is None:
                labels[name] = (address, filename)

        next_address = address + len(code.split())

    for read_into in (patch, validation):
        for address, filename in sorted(read_into):
            code = read_into[address, filename]
            for name in sorted(labels, key=lambda l: (-len(l), l)):
                if name in code:
                    target_address, target_filename = labels[name]
                    assert target_filename == filename
                    jump = target_address - (address + 2)
                    if jump < 0:
                        jump = 0x100 + jump
                    if not 0 <= jump <= 0xFF:
                        raise Exception("Label out of range %x - %s" % (address, code))
                    code = code.replace(name, "%x" % jump)

            code = bytearray(map(lambda s: int(s, 0x10), code.split()))
            read_into[address, filename] = code

    f.close()
    return patch, validation


def select_patches():
    if not OPTION_FILENAMES:
        return

    print("\nThe following optional patches are available.")
    for i, patchfilename in enumerate(OPTION_FILENAMES):
        print("%s: %s" % (i + 1, patchfilename.split(".")[0]))
    print()
    s = input(
        "Select which patches to use, separated by a space."
        "\n(0 for none, blank for all): "
    )
    print()
    s = s.strip()
    if not s:
        return
    while "  " in s:
        s = s.replace("  ", " ")
    numbers = map(int, s.split())
    options = [o for (i, o) in enumerate(OPTION_FILENAMES) if i + 1 in numbers]
    not_chosen = set(OPTION_FILENAMES) - set(options)
    for pfn in not_chosen:
        PATCH_FILENAMES.remove(pfn)


def write_patch(outfile, patchfilename, noverify=None, force=False):
    if patchfilename in ALREADY_PATCHED and not force:
        return
    if noverify and patchfilename not in NOVERIFY_PATCHES:
        NOVERIFY_PATCHES.append(patchfilename)
    elif noverify is None and patchfilename in NOVERIFY_PATCHES:
        noverify = True
    patchpath = path.join(tblpath, patchfilename)
    pf = open(patchpath, "r+b")
    magic_word = pf.read(5)
    pf.close()
    f = get_open_file(outfile)
    if magic_word == b"\xff\xbcCMP":
        CMP_PATCH_FILENAMES.append(patchfilename)
        return write_cmp_patch(f, patchpath)

    patch, validation = patch_filename_to_bytecode(patchpath)
    for patchdict in (validation, patch):
        for (address, filename), code in sorted(patchdict.items()):
            if filename is None:
                f = get_open_file(outfile)
            else:
                if PSX_FILE_MANAGER is None:
                    create_psx_file_manager(outfile)
                f = get_open_file(filename, sandbox=True)
            f.seek(address)

            if patchdict is validation:
                validate = f.read(len(code))
                if validate != code[: len(validate)]:
                    error = "Patch %s-%x did not pass validation." % (
                        patchfilename,
                        address,
                    )
                    if noverify:
                        print("WARNING: %s" % error)
                    else:
                        raise Exception(error)
            else:
                assert patchdict is patch
                f.write(code)

    if patchfilename not in PATCH_FILENAMES:
        PATCH_FILENAMES.append(patchfilename)
    ALREADY_PATCHED.add(patchfilename)


def write_cmp_patch(outfile, patchfilename, verify=False):
    from randomtools.interface import get_sourcefile

    sourcefile = open(get_sourcefile(), "r+b")
    patchfile = open(patchfilename, "r+b")
    magic_word = patchfile.read(5)
    if magic_word != b"\xff\xbcCMP":
        raise Exception("Not a CMP patch.")
    version = ord(patchfile.read(1))
    pointer_length = ord(patchfile.read(1))

    while True:
        command = patchfile.read(1)
        if not command:
            break
        if command == b"\x00":
            address = read_multi(patchfile, length=pointer_length)
            outfile.seek(address)
        elif command == b"\x01":
            chunksize = read_multi(patchfile, length=2)
            address = read_multi(patchfile, length=pointer_length)
            sourcefile.seek(address)
            s = sourcefile.read(chunksize)
            if not verify:
                outfile.write(s)
            elif verify:
                s2 = outfile.read(len(s))
                if s != s2:
                    raise Exception(
                        "Patch write conflict %s %x"
                        % (patchfilename, outfile.tell() - len(s2))
                    )
        elif command == b"\x02":
            chunksize = read_multi(patchfile, length=2)
            s = patchfile.read(chunksize)
            if not verify:
                outfile.write(s)
            elif verify:
                s2 = outfile.read(len(s))
                if s != s2:
                    raise Exception(
                        "Patch write conflict %s %x"
                        % (patchfilename, outfile.tell() - len(s2))
                    )
        else:
            raise Exception("Unexpected EOF")

    sourcefile.close()
    patchfile.close()


def write_patches(outfile):
    if not PATCH_FILENAMES:
        return

    print("Writing patches...")
    for patchfilename in PATCH_FILENAMES:
        write_patch(outfile, patchfilename)


def verify_patches(outfile):
    if not PATCH_FILENAMES:
        return

    print("Verifying patches...")
    f = get_open_file(outfile)
    for patchfilename in PATCH_FILENAMES:
        if patchfilename in NOVERIFY_PATCHES:
            continue
        patchpath = path.join(tblpath, patchfilename)
        if patchfilename in CMP_PATCH_FILENAMES:
            write_cmp_patch(f, patchpath, verify=True)
            continue
        patch, validation = patch_filename_to_bytecode(patchpath)
        for (address, filename), code in sorted(patch.items()):
            if filename is None:
                f = get_open_file(outfile)
            else:
                f = get_open_file(filename, sandbox=True)
            f.seek(address)
            written = f.read(len(code))
            if code != written:
                raise Exception("Patch %x conflicts with modified data." % address)


def get_activated_patches():
    return list(PATCH_FILENAMES)


def sort_good_order(objects):
    objects = sorted(objects, key=lambda o: o.__name__)
    objects = [o for o in objects if o.__name__ in TABLE_SPECS]
    while True:
        changed = False
        for o in list(objects):
            if hasattr(o, "after_order"):
                index = objects.index(o)
                for o2 in o.after_order:
                    index2 = objects.index(o2)
                    if index2 > index:
                        objects.remove(o)
                        objects.insert(index2, o)
                        changed = True
        if not changed:
            break
    return objects


def set_random_degree(value):
    global RANDOM_DEGREE
    RANDOM_DEGREE = value


def get_random_degree():
    global RANDOM_DEGREE
    return RANDOM_DEGREE


def set_difficulty(value):
    global DIFFICULTY
    DIFFICULTY = value


def get_difficulty():
    global DIFFICULTY
    return DIFFICULTY


def gen_random_normal(random_degree=None):
    if random_degree is None:
        random_degree = get_random_degree()
    value_a = (random.random() + random.random() + random.random()) / 3.0
    value_b = random.random()
    value_c = 0.5
    if random_degree > 0.5:
        factor = (random_degree * 2) - 1
        return (value_a * (1 - factor)) + (value_b * factor)
    else:
        factor = random_degree * 2
        return (value_c * (1 - factor)) + (value_a * factor)


def mutate_normal(
    base, minimum, maximum, random_degree=None, return_float=False, wide=False
):
    assert minimum <= base <= maximum
    if minimum == maximum:
        return base
    if random_degree is None:
        random_degree = get_random_degree()
    baseval = base - minimum
    width = maximum - minimum
    factor = gen_random_normal(random_degree=random_degree)
    maxwidth = max(baseval, width - baseval)
    minwidth = min(baseval, width - baseval)
    if wide:
        subwidth = maxwidth
    else:
        width_factor = 1.0
        for _ in range(7):
            width_factor *= random.uniform(random_degree, width_factor)
        subwidth = (minwidth * (1 - width_factor)) + (maxwidth * width_factor)
    if factor > 0.5:
        subfactor = (factor - 0.5) * 2
        modifier = subwidth * subfactor
        value = baseval + modifier
    else:
        subfactor = 1 - (factor * 2)
        modifier = subwidth * subfactor
        value = baseval - modifier
    value += minimum
    if not return_float:
        value = int(round(value))
    if value < minimum or value > maximum:
        return mutate_normal(
            base,
            minimum,
            maximum,
            random_degree=random_degree,
            return_float=return_float,
            wide=wide,
        )
    return value


def shuffle_normal(candidates, random_degree=None, wide=False):
    if random_degree is None:
        classes = list(set([c.__class__ for c in candidates]))
        if len(classes) == 1 and hasattr(classes[0], "random_degree"):
            random_degree = classes[0].random_degree
        else:
            random_degree = get_random_degree()
    max_index = len(candidates) - 1
    new_indexes = {}
    for i, c in enumerate(candidates):
        new_index = mutate_normal(
            i, 0, max_index, return_float=True, random_degree=random_degree, wide=wide
        )
        # new_index = (i * (1-random_degree)) + (new_index * random_degree)
        new_indexes[c] = new_index
    if candidates and hasattr(candidates[0], "signature"):
        shuffled = sorted(candidates, key=lambda c: (new_indexes[c], c.signature))
    else:
        shuffled = sorted(
            candidates, key=lambda c: (new_indexes[c], random.random(), c)
        )
    return shuffled


def shuffle_simple(candidates, random_degree=None):
    assert 0 <= random_degree <= 1
    if random_degree is None:
        classes = list(set([c.__class__ for c in candidates]))
        if len(classes) == 1 and hasattr(classes[0], "random_degree"):
            random_degree = classes[0].random_degree
        else:
            random_degree = get_random_degree()

    max_index = len(candidates) - 1
    indexes = list(range(len(candidates)))
    pure_shuffled = list(indexes)
    random.shuffle(pure_shuffled)
    new_indexes = list(indexes)

    for _ in range(len(indexes)):
        for i, v in enumerate(new_indexes):
            v += random.choice([1, -1])
            new_indexes[i] = v

    if random_degree == 0.5:
        final_indexes = new_indexes
    elif random_degree < 0.5:
        factor = random_degree * 2
        final_indexes = [
            ((1 - factor) * a) + (factor * b) for (a, b) in zip(indexes, new_indexes)
        ]
    elif random_degree > 0.5:
        factor = (random_degree - 0.5) * 2
        final_indexes = [
            ((1 - factor) * a) + (factor * b)
            for (a, b) in zip(new_indexes, pure_shuffled)
        ]

    assert len(candidates) == len(indexes) == len(final_indexes)
    shuffled = [candidates[i] for (f, i) in sorted(zip(final_indexes, indexes))]

    return shuffled


class classproperty(property):
    def __get__(self, inst, cls):
        return self.fget(cls)


class CachedProperty(ABC):
    property_cache: dict[str, Any]


def cached_property(fn: Callable) -> property:
    @property
    def inner(self: CachedProperty):
        if not hasattr(self, "_property_cache"):
            self.property_cache = {}

        if fn.__name__ not in self.property_cache:
            self.property_cache[fn.__name__] = fn(self)

        return self.property_cache[fn.__name__]

    return inner


# TODO: remove
class EventList:
    def __init__(self, pointer: int, meo: "MapEventObject"):
        self.pointer = pointer
        self.meo = meo
        if self.pointer == self.meo.npc_pointer:
            self.script_pointers = [(None, self.pointer)]
            return

        f = get_open_file(get_outfile())
        f.seek(pointer)
        self.script_pointers = []
        while True:
            index = ord(f.read(1))
            if index == 0xFF:
                break
            script_pointer = int.from_bytes(f.read(2), byteorder="little")
            self.script_pointers.append(
                (index, self.meo.eventlists_pointer + script_pointer)
            )
        MapEventObject.deallocate((self.pointer, f.tell()))

    def __repr__(self):
        s = ""
        for script in self.scripts:
            s += "\n" + script.pretty_with_header + "\n"
        return s.strip()

    @cached_property
    def index(self):
        i = self.meo.event_lists.index(self)
        return "XABCDEF"[i]

    @property
    def map_meta(self):
        return self.meo.map_meta

    @property
    def eventlists_pointer(self):
        return self.meo.eventlists_pointer

    @property
    def size_estimate(self):
        if self.index == "X":
            return len(self.script.data)
        total = (len(self.scripts) * 3) + 1
        for script in self.scripts:
            total += len(script.data)
        return total

    def get_script_by_index(self, index):
        if self.index == "X":
            assert index is None
            assert len(self.scripts) == 1
            return self.scripts[0]

        candidates = [s for s in self.scripts if s.index == index]
        if len(candidates) == 1:
            return candidates[0]
        return None

    def get_or_create_script_by_index(self, index):
        script = self.get_script_by_index(index)
        if script:
            return script

        script = Script(None, 0, self, index=index)
        self.scripts.append(script)
        return script

    def read_scripts(self):
        self.scripts = []
        all_pointers = sorted(MapEventObject.ALL_POINTERS)
        for index, p1 in sorted(self.script_pointers):
            p2 = next(p for p in all_pointers if p > p1)
            script = Script(p1, p2 - p1, self, index=index)
            script.deallocate()
            self.scripts.append(script)
        if args.args.debug:
            for script in self.scripts:
                if script.frozen:
                    continue
                script.data = script.compile()
                script.script = script.parse()
                script.import_script(script.pretty)
                assert script.validate_no_change()
                script.script = script.old_script

    def write(self):
        for script in self.scripts:
            assert script.event_list is self
            script.realign_addresses()
        f = get_open_file(get_outfile())

        npc_loader = self.index == "X"
        if npc_loader:
            assert len(self.scripts) == 1
            script = self.scripts[0]
            data = script.compile(optimize=True)
            assert data[-1] == 0
            self.pointer = MapEventObject.allocate(len(data), npc_loader=npc_loader)
            script.script_pointer = self.pointer
            script.data = script.compile(optimize=True)
            f.seek(script.script_pointer)
            f.write(script.data)
            assert f.tell() == self.pointer + len(data)
            return

        self.pointer = MapEventObject.allocate(
            (len(self.scripts) * 3) + 1, near=self.meo.eventlists_pointer
        )
        f.seek(self.pointer)

        if not hasattr(self.meo, "assigned_zero"):
            for i, script in enumerate(self.scripts):
                if script.index == 0:
                    self.meo.assigned_zero = self.pointer + (i * 3)

        for i, script in enumerate(self.scripts):
            data = script.compile(optimize=True, ignore_pointers=True)
            assert data[-1] == 0
            if data[0] == 0 and hasattr(self.meo, "assigned_zero"):
                assert data == b"\x00"
                assert hasattr(self.meo, "assigned_zero")
                if args.args.debug and self.meo.assigned_zero != self.pointer + (i * 3):
                    f.flush()
                    f.seek(self.meo.assigned_zero)
                    peek = f.read(1)
                    assert peek == b"\x00"
                script.script_pointer = self.meo.assigned_zero
            else:
                script.script_pointer = MapEventObject.allocate(
                    len(data),
                    npc_loader=npc_loader,
                    find_best_fit_dry=True,
                    near=[self.meo.eventlists_pointer, self.pointer],
                )
                assert (
                    0 <= script.script_pointer - self.meo.eventlists_pointer <= 0xFFFF
                )
                assert 0 <= script.script_pointer - self.pointer <= 0xFFFF
                script.data = script.compile(optimize=True)
                # assert len(script.data) == len(data)
                MapEventObject.allocate(
                    len(script.data),
                    npc_loader=npc_loader,
                    forced=script.script_pointer,
                )
                f.seek(script.script_pointer)
                f.write(script.data)
                assert b"\x00" in script.data
                if not hasattr(self.meo, "assigned_zero"):
                    zero_index = script.data.index(b"\x00")
                    self.meo.assigned_zero = script.script_pointer + zero_index
            script_pointer = script.script_pointer
            offset = script_pointer - self.meo.eventlists_pointer
            assert 0 <= offset <= 0xFFFF
            f.seek(self.pointer + (3 * i))
            f.write(bytes([script.index]))
            f.write(offset.to_bytes(2, byteorder="little"))
        f.write(b"\xff")
        assert f.tell() == self.pointer + (3 * len(self.scripts)) + 1
        if args.args.debug and hasattr(self.meo, "assigned_zero"):
            f.seek(self.meo.assigned_zero)
            peek = f.read(1)
            assert peek == b"\x00"


class Address:
    def __init__(self, address: int, is_local: bool):
        assert 0 <= address <= 0x7FFF
        self.address = address
        self.old_address = address
        self.is_local = is_local
        if not is_local:
            raise NotImplementedError("Non-local address.")

    def __repr__(self):
        return "{0}{1:X}".format("@" if self.is_local else "&", self.address)

    def __copy__(self):
        # TODO: test without this method.
        return self(self.address, self.is_local)  # type: ignore


type TextType = list[tuple[str | int | None, bytes]]
type SingleParam = int | Address | str | TextType | None
type ParamsType = list[SingleParam] | str
type ScriptType = list[
    tuple[
        int,  # Line number
        int,  # OP Code
        ParamsType,
    ]
]


# TODO: transform to output required binary data (for asar?)
class Script:
    text: TextType
    script: ScriptType
    data: bytes

    INSTRUCTIONS_FILENAME = path.join(tblpath, "event_instructions.txt")
    FULL_PARAMETERS: dict[int, list[int | str]] = {}  # int == opcode
    COMMENTS: dict[int, str] = {}

    for line in read_lines_nocomment(INSTRUCTIONS_FILENAME):
        while "  " in line:
            line = line.replace("  ", " ")
        line = line.split(" ", 2)
        if len(line) == 2:
            opcode, num_parameters = line
            comment = None
        else:
            opcode, num_parameters, comment = line
        opcode = int(opcode, 0x10)
        temp = num_parameters.split(",")
        temp = [int(p) if p in digits else p for p in temp]
        temp = [p for p in temp if p != 0]
        FULL_PARAMETERS[opcode] = temp
        if comment:
            COMMENTS[opcode] = comment

    LINE_MATCHER = re.compile(r"^\s*([0-9a-fA-F]{1,4})\.", flags=re.MULTILINE)
    ADDRESS_MATCHER = re.compile(r"@([0-9A-Fa-f]+)[^0-9A-Fa-f]", flags=re.DOTALL)

    def __init__(
        self,
        script_pointer: int | None,
        data_length: int,
        event_list: EventList,
        index: int | None = None,
    ):
        self.event_list = event_list
        self.index = index
        self.frozen = False

        if script_pointer is not None:
            self.script_pointer = script_pointer
            f = get_open_file(get_outfile())
            f.seek(self.script_pointer)
            self.data = f.read(data_length)
        else:
            self.data = b""
            self.script_pointer = self.base_pointer

        self.old_script_pointer = self.script_pointer
        self.old_base_pointer = self.base_pointer
        self.old_data = self.data

        self.script = self.parse()
        self.old_script = deepcopy(self.script)
        self.old_pretty = self.pretty

    def __repr__(self):
        return self.pretty_with_header

    @property
    def eventlists_pointer(self):
        return self.event_list.eventlists_pointer

    @property
    def map_meta(self):
        return self.event_list.map_meta

    @property
    def is_npc_load_event(self):
        return self.index is None

    @property
    def base_pointer(self):
        if not self.is_npc_load_event:
            return self.eventlists_pointer
        else:
            return self.script_pointer & 0xFF8000

    @property
    def pretty(self):
        pretty = self.prettify_script(self.script)
        address_matches = ADDRESS_MATCHER.findall(pretty)
        address_matches = sorted(set(int(match, 0x10) for match in address_matches))
        done_labels = set()
        for offset in reversed(address_matches):
            if offset in done_labels:
                continue
            done_labels.add(offset)
            line_code = "{0:0>4X}. ".format(offset)
            try:
                _index = pretty.index(line_code)
                replacement = "# LABEL @{0:X} ${1:x}\n{2}".format(
                    offset, self.script_pointer + offset, line_code
                )
                pretty = pretty.replace(line_code, replacement)
            except ValueError:
                to_replace = "@{0:X}".format(offset)
                replacement = "@{0:X}!".format(offset)
                pretty = pretty.replace(to_replace, replacement)

        return pretty.rstrip()

    @property
    def header(self):
        header = "EVENT {0}  # ${1:x}:{2:x}".format(
            self.signature, self.event_list.pointer, self.script_pointer
        )
        return header

    @property
    def signature(self):
        if self.index is not None:
            si = "{0:0>2X}".format(self.index)
        else:
            si = "XX"
        return "{0:0>2X}-{1}-{2}".format(
            self.event_list.meo.index, self.event_list.index, si
        )

    @property
    def pretty_with_header(self):
        s = "{0}\n{1}".format(self.header, self.pretty)
        s = s.replace("\n", "\n  ")
        return s.strip()

    @property
    def op_count(self):
        return Counter([opcode for _, opcode, _ in self.script])

    @cached_property
    def pre_data(self):
        pointer = self.script_pointer - 0x1000
        assert pointer >= 0
        f = get_open_file(get_outfile())
        f.seek(pointer)
        return f.read(0x1000)

    @classmethod
    def get_pretty_variable(cls, variable: Any) -> str:
        var_name = "Variable {0:0>2X} (${1:0>4x})".format(variable, variable + 0x079E)
        return var_name

    @classmethod
    def get_pretty_flag(cls, flag: int):
        address = 0x77E + (flag // 8)
        bit = 1 << (flag % 8)
        fname = "Flag {0:0>2X} (${1:0>4x}:{2:0>2x})".format(flag, address, bit)
        return fname

    @staticmethod
    def shift_line_numbers(script_text: str, offset: int):
        new_text: list[str] = []
        for line in script_text.split("\n"):
            if ". " in line and ("(" in line or ":" in line):
                line = line.lstrip()
                if "." in line[:5] and line[0] != "#":
                    while line[4] != ".":
                        line = "0" + line
            new_text.append(line)
        script_text = "\n".join(new_text)

        lines: list[str] = Script.LINE_MATCHER.findall(script_text)
        for line in lines:
            value = int(line, 0x10)
            assert value < offset
            line = "{0:0>4X}".format(value)
            replacement = "{0:0>4X}".format(value + offset)
            script_text = script_text.replace(
                "%s. " % line.upper(), "%s. " % replacement
            )
            script_text = script_text.replace(
                "%s. " % line.lower(), "%s. " % replacement
            )
        lines = Address_MATCHER.findall(script_text)
        lines = sorted(lines, key=lambda l: -int(line, 0x10))
        for line in lines:
            value = int(line, 0x10)
            assert value < offset
            replacement = "{0:X}".format(value + offset)
            script_text = re.sub(r"@%s(\W)" % line, r"@%s\1" % replacement, script_text)
        return script_text

    def prettify_script(self, script: ScriptType) -> str:
        if not hasattr(MapEventObject, "_script_cache"):
            MapEventObject.script_cache = {}
        key = str(script)
        if key in MapEventObject.script_cache:
            return MapEventObject.script_cache[key]

        pretty = ""
        for line_number, opcode, parameters in script:
            line = ""
            if self.FULL_PARAMETERS[opcode] == ["text"]:
                text = MapEventObject.prettify_text(parameters)
                textlines = text.split("\n")
                justifiers = ["{0:0>2X}:".format(opcode)]
                justifiers += [""] * len(textlines)
                for left, right in zip(justifiers, textlines):
                    line += "{0:3} {1}\n".format(left, right)
                line = line.rstrip()
                line = line.replace("\n", "\n      ")
                line = "{0:0>4X}. {1}".format(line_number, line)
            else:
                if len(parameters) > 16:
                    paramstr = hexify(parameters[:16])
                    paramstr += "... [{0} bytes]".format(len(parameters))
                else:
                    params = []
                    parameter_types = list(self.FULL_PARAMETERS[opcode])
                    if "variable" in parameter_types and parameters[0] in {0xC0, 0xC2}:
                        assert len(parameter_types) == 1
                        parameter_types += [2, 2]
                    while len(parameter_types) < len(parameters):
                        if isinstance(parameter_types[-1], int):
                            assert "variable" in parameter_types
                            parameter_types.append(1)
                        else:
                            parameter_types.append(parameter_types[-1])

                    for pt, p in zip(parameter_types, parameters):
                        if isinstance(p, int):
                            if pt in ["pointers", "variable"]:
                                pt = 1
                            assert isinstance(pt, int)
                            assert pt > 0
                            s = ("{0:0>%sX}" % (pt * 2)).format(p)
                        else:
                            assert isinstance(p, Address)
                            s = str(p)
                        params.append(s)
                    paramstr = "-".join(params)
                line = "{0:0>2X}({1})".format(opcode, paramstr)

                # determine custom comments
                if opcode in self.COMMENTS:
                    comment = self.COMMENTS[opcode]
                else:
                    comment = ""

                if opcode in [0x68, 0x7B]:
                    npc_index, sprite_index = parameters
                    if self.map_meta:
                        position = self.map_meta.get_npc_position_by_index(
                            npc_index - 0x4F
                        )
                    else:
                        position = None
                    name = names.sprites[sprite_index]
                    if position:
                        x, y = position.x, position.y
                        x = "{0:0>2x}".format(x)
                        y = "{0:0>2x}".format(y)
                    else:
                        x, y = "??", "??"
                    comment += " ({0},{1}) {2:0>2x}: {3:0>2x} {4}".format(
                        x, y, npc_index, sprite_index, name
                    )
                    comment += "\n"
                elif opcode == 0x53:
                    (formation_index,) = parameters
                    f = BossFormationObject.get(formation_index)
                    comment = "{0} ({1})".format(comment, f.name)
                elif opcode in {0x20, 0x21}:
                    item_index, quantity = parameters
                    item_index |= 0x100 * (opcode - 0x20)
                    item = ItemObject.get(item_index)
                    comment = "{0} ({1} x{2})".format(comment, item.name, quantity)
                elif opcode == 0x23:
                    character_index, spell_index = parameters
                    character = CharacterObject.get(character_index)
                    spell = SpellObject.get(spell_index)
                    comment = "{0} ({1}: {2})".format(
                        comment, character.name, spell.name
                    )
                elif opcode == 0x16:
                    event = "[{0:0>2X}-B-{1:0>2X}] ({2:0>2X})".format(*parameters)
                    comment = "{0} {1}".format(comment, event)
                elif opcode == 0x35:
                    assert parameters[0] >= 0x10
                    xnpc = RoamingNPCObject.get(parameters[0] - 0x10)
                    npc_signature = "({0:0>2X} {1})".format(
                        parameters[0], xnpc.sprite_name
                    )
                    loc_signature = "(map {0:0>2X}, NPC {1:0>2X})".format(
                        parameters[1], parameters[2]
                    )
                    comment = "Move roaming NPC {0} to {1}".format(
                        npc_signature, loc_signature
                    )
                    comment += " [{0:0>2X}-C-{1:0>2X}]".format(
                        parameters[1], parameters[0]
                    )
                    roaming_comment = "[{0}] {1}".format(self.signature, comment)
                    MapEventObject.roaming_comments.add(roaming_comment)
                elif opcode == 0x8C:
                    a = "Load animation frame {0:0>2X}-{1:0>2X}".format(
                        parameters[1], parameters[2]
                    )
                    b = "for sprite {0:0>2X}".format(parameters[0])
                    comment = "{0} {1}".format(a, b)
                elif opcode == 0x14:
                    assert parameters[-3] in {0x20, 0x30}
                    assert isinstance(parameters[-2], Address)
                    assert parameters[-1] == 0xFF
                    conditions = parameters[:-3]
                    s = "If"
                    while conditions:
                        c = conditions.pop(0)
                        if c == 0xF0:
                            s += " NPC ???"
                            conditions.pop(0)
                            conditions.pop(0)
                        elif c == 0xF8:
                            npc_index = conditions.pop(0)
                            assert npc_index >= 1
                            s += " NPC {0:0>2X} ???".format(npc_index - 1)
                            conditions.pop(0)
                        elif c in {0xC0, 0xC2}:
                            item_index = conditions.pop(0)
                            item_name = ItemObject.get(item_index).name
                            quantity = conditions.pop(0)
                            if c == 0xC0:
                                s += " exactly {0} x{1} owned".format(
                                    item_name, quantity
                                )
                            elif c == 0xC2:
                                s += " at least {0} x{1} owned".format(
                                    item_name, quantity
                                )
                        elif c in {0x10, 0x12}:
                            variable = conditions.pop(0)
                            value = conditions.pop(0)
                            vname = self.get_pretty_variable(variable)
                            if c == 0x10:
                                s += " {0} == {1}".format(vname, value)
                            elif c == 0x12:
                                s += " {0} >= {1}".format(vname, value)
                        else:
                            assert c in {0x00, 0x40, 0x80, 0x01, 0x41, 0x81}
                            if c & 0x40:
                                s += " OR"
                            elif c & 0x80:
                                s += " AND"
                            flag = conditions.pop(0)
                            s += " " + self.get_pretty_flag(flag)
                            if c & 1:
                                s += " NOT"
                            s += " set"
                    if parameters[-3] == 0x30:
                        s += " then DON'T jump to {0}".format(parameters[-2])
                    elif parameters[-3] == 0x20:
                        s += " then jump to {0}".format(parameters[-2])
                    comment = s.strip()
                    assert "  " not in comment

                if comment.endswith("Flag"):
                    flag = parameters[0]
                    comment = comment.replace("Flag", self.get_pretty_flag(flag))

                if comment.endswith("Variable"):
                    variable = parameters[0]
                    comment = comment.replace(
                        "Variable", self.get_pretty_variable(variable)
                    )

                if comment.strip():
                    line = "{0:0>4X}. {1:30} # {2}".format(line_number, line, comment)
                else:
                    line = "{0:0>4X}. {1}".format(line_number, line)
            pretty += line.rstrip() + "\n"

        MapEventObject.script_cache[key] = pretty.rstrip()
        return self.prettify_script(script)

    def make_pointer(self, data: bytes):
        assert len(data) == 2
        offset = int.from_bytes(data, byteorder="little")
        pointer = self.base_pointer + offset
        is_local_pointer = (
            self.script_pointer <= pointer < self.script_pointer + len(self.data)
        )
        if is_local_pointer:
            script_offset = self.script_pointer - self.base_pointer
            return Address(offset - script_offset, is_local_pointer)
        else:
            return Address(pointer, is_local_pointer)

    def parse_text(self, opcode: int, data: bytes, full_data: bytes | None = None):
        if full_data is None:
            full_data = self.data

        text: TextType = []
        if opcode == 0x13:
            npc_index, data = data[:1], data[1:]
            text.append(("NPC", npc_index))
        elif opcode in {0x6D, 0x6E}:
            position, data = data[:2], data[2:]
            text.append(("POSITION", position))
        elif opcode == 0x9E:
            unknown, data = data[:1], data[1:]
            text.append(("POSITION", unknown))
        text.append((None, b""))

        while True:
            try:
                textcode, data = data[0], data[1:]
            except IndexError:
                break

            if textcode in MapEventObject.TEXT_TERMINATORS:
                text.append((textcode, b""))
                break
            elif textcode == 0xA:
                n = MapEventObject.TEXT_PARAMETERS[textcode]
                text_parameters, data = data[:n], data[n:]
                value = int.from_bytes(text_parameters, byteorder="little")
                length = (value >> 12) + 2
                pointer = (value & 0xFFF) + 2
                consumed_data = full_data[: -len(data)]
                buffer_data = self.pre_data + consumed_data
                index = len(buffer_data) - pointer
                assert index >= 0
                repeat_text = buffer_data[index : index + length]
                assert len(repeat_text) == length
                text.append((None, repeat_text))

            elif textcode in MapEventObject.TEXT_PARAMETERS:
                n = MapEventObject.TEXT_PARAMETERS[textcode]
                text_parameters, data = data[:n], data[n:]
                assert len(text_parameters) == n
                text.append((textcode, text_parameters))
            else:
                if text[-1][0] is not None:
                    text.append((None, b""))
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
    def trim_script(cls, script: ScriptType):
        for i in range(len(script) - 1, -1, -1):
            _, opcode, parameters = script[i]
            if opcode == 0:
                assert not parameters
                script = script[: i + 1]
                break
            elif "text" in cls.FULL_PARAMETERS[opcode]:
                # self.CHARACTER_MAP[parameters[-1][-1]] == '<END EVENT>'
                charcode = parameters[-1][0]
                if MapEventObject.CHARACTER_MAP[charcode] == "<END EVENT>":
                    break
        else:
            raise AssertionError("Script does not terminate.")
        return script

    def parse(self, data: bytes | None = None) -> ScriptType:
        if self.frozen:
            return self.old_script

        if data is None:
            data = self.data

        full_data = data
        script: ScriptType = []
        try:
            while data:
                consumed = len(full_data) - len(data)
                opcode, data = data[0], data[1:]
                assert opcode in self.FULL_PARAMETERS
                parameter_types = self.FULL_PARAMETERS[opcode]
                parameters: list[Any] = []
                for pt in parameter_types:
                    assert pt != 0
                    if pt == "text":
                        # repeat_pointer = self.script_pointer + consumed + 1  # Unused
                        text, data = self.parse_text(opcode, data)
                        parameters.extend(text)
                    elif pt == "pointers":
                        num_pointers, data = data[0], data[1:]
                        parameters.append(num_pointers)
                        for _ in range(num_pointers):
                            pointer = self.make_pointer(data[:2])
                            data = data[2:]
                            parameters.append(pointer)
                    elif pt == "variable":
                        assert opcode == 0x14
                        while True:
                            c, data = data[0], data[1:]
                            parameters.append(c)
                            if c == 0xFF:
                                break
                            elif c & 0xF0 == 0xF0:
                                assert len(parameters) == 1
                                assert c in {0xF0, 0xF8}
                                # 0xf0 Monster on button
                                # 0xf8 if NPC state
                                parameters.append(data[0])
                                parameters.append(data[1])
                                data = data[2:]
                            elif c & 0xF0 == 0xC0:
                                # ???
                                assert len(parameters) == 1
                                assert c in {0xC0, 0xC2}
                                # 0xc0 Check item possessed exactly number
                                # 0xc2 Check item possessed GTE
                                item_index, data = data[:2], data[2:]
                                item_number, data = data[:2], data[2:]
                                item_index = int.from_bytes(
                                    item_index, byteorder="little"
                                )
                                item_number = int.from_bytes(
                                    item_number, byteorder="little"
                                )
                                parameters.append(item_index)
                                parameters.append(item_number)
                            elif c & 0xF0 == 0x10:
                                assert len(parameters) == 1
                                assert c in {0x10, 0x12}
                                # 0x10 Equals
                                # 0x12 GTE
                                parameters.append(data[0])
                                parameters.append(data[1])
                                data = data[2:]
                            elif c & 0xE0 == 0x20:
                                assert c in {0x20, 0x30}
                                # 0x20 Branch if True
                                # 0x30 Branch if False
                                pointer = self.make_pointer(data[:2])
                                data = data[2:]
                                parameters.append(pointer)
                            else:
                                assert c in {0x00, 0x01, 0x40, 0x41, 0x80, 0x81}
                                # 0x01 NOT
                                # 0x40 OR
                                # 0x80 AND
                                flag, data = data[0], data[1:]
                                parameters.append(flag)
                    elif pt == "addr":
                        pointer = self.make_pointer(data[:2])
                        data = data[2:]
                        parameters.append(pointer)
                    else:
                        assert isinstance(pt, int)
                        assert pt > 0
                        assert len(data) >= pt
                        parameter, data = data[:pt], data[pt:]
                        parameter = int.from_bytes(parameter, byteorder="little")
                        parameters.append(parameter)
                if not script:
                    assert consumed == 0
                else:
                    assert consumed > 0
                script.append((consumed, opcode, parameters))
                if script == [(0, 0, [])]:
                    break
        except AssertionError:
            print("WARNING: Script {0:x}.".format(self.script_pointer))
            try:
                script = self.trim_script(script)
            except AssertionError:
                print(
                    "WARNING: Script {0:x} does not terminate.".format(
                        self.script_pointer
                    )
                )
                script.append((len(full_data), 0, []))
        return script

    def import_script(self, text: str, warn_double_import: bool = True):
        warn_double_import = warn_double_import or args.args.debug
        assert not self.frozen
        if warn_double_import and hasattr(self, "_imported") and self._imported:
            print("WARNING: Script {0:x} double imported.".format(self.script_pointer))
        self._imported = True

        line_matcher = re.compile(r"^ *([0-9A-Fa-f]+)\. (.*)$")
        lines: list[tuple[int, str]] = []
        prev_number = None
        prev_line: str | None = None
        seen_line_numbers = set()
        for line in text.split("\n"):
            if "#" in line:
                line = line.split("#")[0]
            line = line.rstrip()
            if not line:
                continue
            match = line_matcher.match(line)
            if lines:
                prev_number, prev_line = lines[-1]
            if match:
                line_number = int(match.group(1), 0x10)
                if prev_number is not None and prev_number >= line_number:
                    print(text)
                    raise Exception(
                        "SCRIPT {0} {1:x} ERR: Lines out of order.".format(
                            self.signature, self.script_pointer
                        )
                    )
                lines.append((line_number, match.group(2)))
                seen_line_numbers.add(line_number)
            else:
                lines[-1] = (prev_number, "\n".join([prev_line, line.strip()]))  # type: ignore  # ignore .join() type error

        script: ScriptType = []
        line_number = None
        line = ""
        try:
            for line_number, line in lines:
                assert line[2] in "(:"
                opcode = int(line[:2], 0x10)
                if line[2] == "(":
                    assert line[-1] == ")"
                    parameters = line[3:-1]
                    assert "(" not in parameters and ")" not in parameters
                    if parameters:
                        parameters = parameters.split("-")
                    else:
                        parameters = []
                    params: ParamsType = []
                    for p in parameters:
                        if p.startswith("@"):
                            offset = int(p[1:], 0x10)
                            is_local = offset in seen_line_numbers
                            assert is_local
                            addr = Address(address=offset, is_local=is_local)
                            params.append(addr)
                        else:
                            params.append(int(p, 0x10))
                    script.append((line_number, opcode, params))
                elif line[2] == ":":
                    linetext = line[3:].strip()
                    compress = opcode not in {0x6D, 0x6E}
                    newtext = MapEventObject.reverse_prettify_text(
                        linetext, compress=compress
                    )
                    newscript = self.parse(bytes([opcode]) + newtext)
                    newpretty = self.prettify_script(newscript)
                    for linetextline in linetext.split("\n"):
                        assert linetextline in newpretty
                    assert len(newscript) == 1
                    _new_number, new_op, new_params = newscript[0]
                    assert new_op == opcode
                    script.append((line_number, opcode, new_params))
        except Exception as e:
            raise Exception(
                "SCRIPT {0:x} ERROR: {1}. {2}".format(
                    self.script_pointer, line_number, line
                )
            ) from e

        self.script = script
        return script

    def compress(self, text: bytes, compress: bool = False):
        assert isinstance(text, bytes)
        old_buffer_length = len(self.compression_buffer)
        while text:
            maxlength = min(17, len(self.compression_buffer), len(text))
            for length in range(maxlength, 3, -1):
                if not compress:
                    continue
                substr = "".join(chr(c) for c in text[:length])
                if any([ord(c) & 0x80 for c in substr]):
                    continue
                if substr not in self.compression_buffer:
                    continue
                sub_data = self.compression_buffer[-0xFFE:]
                sub_data += "\x0a"
                if substr not in sub_data:
                    continue
                pointer = len(sub_data) - sub_data.index(substr)
                length_field = (length - 2) << 12
                assert pointer <= 0xFFF
                assert length_field & pointer == 0
                fields = length_field | pointer
                assert fields <= 0xFFFF
                # Compression is better? Need to test.
                self.compression_buffer += "\x0a"
                self.compression_buffer += chr(fields & 0xFF)
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
        for line, op_code, params in self.script:
            line += offset
            for param in params:
                if isinstance(param, Address):
                    param.address += offset
            new_script.append((line, op_code, params))
        self.script = new_script

    def realign_addresses(self):
        self.normalize_addresses()
        line_numbers = [ln for (ln, _, _) in self.script]
        new_script = []
        for i, (line_number, opcode, parameters) in enumerate(self.script):
            try:
                next_line_number = self.script[i + 1][0]
            except IndexError:
                next_line_number = None
            addresses = [p for p in parameters if isinstance(p, Address)]
            for p in addresses:
                addr = p.address
                if addr not in line_numbers:
                    addr = min([ln for ln in line_numbers if ln >= addr])
                    p.address = addr
            if len(addresses) == 1:
                addr = addresses[0]
                if addr.address == next_line_number:
                    continue
            new_script.append((line_number, opcode, parameters))
        self.script = new_script

    def compile(
        self,
        script: ScriptType | None = None,
        optimize: bool = False,
        ignore_pointers: bool = False,
    ):
        if self.frozen:
            return self.old_data
        if script is None:
            script = self.script
        partial: dict[int, str | list[Address]] = {}
        previous_line_number = None
        self.compression_buffer = ""
        prev_op = None
        assigned_zero = None
        zero_lines = set()
        for line_number, opcode, parameters in script:
            if opcode == 0:
                zero_lines.add(line_number)
                if assigned_zero is None:
                    assigned_zero = line_number
                elif prev_op == 0 and optimize:
                    continue
            prev_op = opcode
            if isinstance(line_number, str):
                line_number = int(line_number, 0x10)
            if previous_line_number is not None:
                assert line_number > previous_line_number
            previous_line_number = line_number

            parameter_types = list(self.FULL_PARAMETERS[opcode])
            if "variable" in parameter_types and parameters[0] in {0xC0, 0xC2}:
                assert len(parameter_types) == 1
                parameter_types += [2, 2]
            while len(parameter_types) < len(parameters):
                if isinstance(parameter_types[-1], int):
                    assert "variable" in parameter_types
                    parameter_types.append(1)
                else:
                    parameter_types.append(parameter_types[-1])
            assert len(parameter_types) == len(parameters)

            line = []

            def append_data(to_append: ParamsType | SingleParam):
                if not isinstance(to_append, list):
                    to_append = [to_append]
                for ta in to_append:
                    if isinstance(ta, Address):
                        line.append(ta)
                        line.append(None)
                        self.compression_buffer += "💙💙"
                    elif isinstance(ta, int):
                        line.append(ta)
                        self.compression_buffer += chr(ta)
                    else:
                        raise Exception("Unexpected data type.")

            append_data(opcode)
            for param_type, parameter in zip(parameter_types, parameters):
                if param_type == "text":
                    label, value = parameter
                    if isinstance(label, int):
                        append_data(label)
                        if value:
                            assert len(value) == 1
                            value = ord(value)
                            assert 0 <= value <= 0xFF
                            append_data(value)
                    elif label is None:
                        assert isinstance(value, bytes)
                        # compress = opcode not in {0x6d, 0x6e}
                        compress = False
                        value = self.compress(value, compress=compress)
                        line += [ord(c) for c in value]
                    elif isinstance(value, bytes):
                        append_data([c for c in value])
                    else:
                        # Should NEVER happen
                        assert False
                        assert isinstance(value, int)
                        assert 0 <= value <= 0xFF
                        append_data(value)
                    continue

                if isinstance(parameter, Address):
                    append_data(parameter)
                elif param_type in ["pointers", "variable"]:
                    append_data(parameter)
                else:
                    assert isinstance(param_type, int)
                    value = parameter.to_bytes(param_type, byteorder="little")
                    append_data([v for v in value])

            partial[line_number] = line

        address_conversions = {}
        running_length = 0
        for line_number in sorted(partial):
            assert running_length >= 0
            address_conversions[line_number] = running_length
            running_length += len(partial[line_number])

        new_data = b""
        for line_number, line in sorted(partial.items()):
            for value in line:
                if isinstance(value, Address) and not ignore_pointers:
                    assert value.is_local
                    if optimize and value.address in zero_lines:
                        value.address = assigned_zero
                    value.address = address_conversions[value.address]

            new_line: list[int] = []
            for value in line:
                if value is None:
                    continue
                elif isinstance(value, Address):
                    script_offset = self.script_pointer - self.base_pointer
                    address = value.address + script_offset
                    if ignore_pointers:
                        address = 0
                    assert 0 <= address <= 0xFFFF
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
        while "  " in old:
            old = old.replace("  ", " ")
        while "  " in new:
            new = new.replace("  ", " ")
        while " \n" in old:
            old = old.replace(" \n", "\n")
        while " \n" in new:
            new = new.replace(" \n", "\n")
        old = re.sub("\n..... ", "\n", old)
        new = re.sub("\n..... ", "\n", new)
        old = re.sub("@[^-)]+", "", old)
        new = re.sub("@[^-)]+", "", new)
        old = old.rstrip()
        new = new.rstrip()
        if args.args.debug and old != new:
            olds = old.split("\n")
            news = new.split("\n")
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
        MapEventObject.deallocate(
            (self.script_pointer, self.script_pointer + len(self.data))
        )

    def optimize(self):
        addresses = [
            a.address
            for (_, _, parameter) in self.script
            for a in parameter
            if isinstance(a, Address)
        ]

        new_script: ScriptType = []
        prev_line_nr: int = MISSING
        prev_op_code: int = MISSING
        prev_param: ParamsType = MISSING
        for line_number, opcode, parameters in self.script:
            if (
                opcode == 0x69
                and opcode == prev_op_code
                and line_number not in addresses
            ):
                new_script.remove((prev_line_nr, prev_op_code, prev_param))
                line_number = prev_line_nr
            new_script.append((line_number, opcode, parameters))
            if opcode == 0 and prev_op_code is MISSING:
                break
            prev_line_nr, prev_op_code, prev_param = line_number, opcode, parameters
        self.script = new_script


class Specs(object):
    total_size: int
    subfile: str
    pointer: int
    count: int
    grouped: bool
    pointed: bool
    delimit: int
    pointer_filename: str

@total_ordering
class TableObject(object):
    pointer: int
    specs: Specs

    class __metaclass__(type):
        def __iter__(self):
            for obj in self.ranked:
                yield obj

    def __init__(
        self,
        filename: str | None = None,
        pointer: int | None = None,
        index: int | None = None,
        groupindex: int = 0,
        size: int | None = None,
    ):
        assert hasattr(self, "specs")
        assert isinstance(self.specs.total_size, int)
        assert index is not None
        if hasattr(self.specs, "subfile"):
            self.filename = path.join(SANDBOX_PATH, self.specs.subfile)
        else:
            self.filename = filename
        if self.filename != GLOBAL_OUTPUT and PSX_FILE_MANAGER is None:
            create_psx_file_manager(filename)
        self.pointer = pointer
        self.groupindex = groupindex
        self.variable_size = size
        self.index = index
        if filename:
            self.read_data(None, pointer)
        key = (type(self), self.index)
        assert key not in GRAND_OBJECT_DICT
        GRAND_OBJECT_DICT[key] = self

    def __hash__(self):
        return hash(self.signature)

    def __eq__(self, other):
        if type(self) is type(other):
            return self.index == other.index
        return False

    def __lt__(self, other):
        if other is None:
            return False
        assert type(self) is type(other)
        return (self.rank, self.index) < (other.rank, other.index)

    @classmethod
    def create_new(cls, filename=None) -> Self:
        if filename is None:
            filename = GLOBAL_OUTPUT
        index = max([o.index for o in cls.every]) + 1
        new = cls(filename=filename, index=index)
        # new.old_data = {}
        for name, size, other in new.specs.attributes:
            if other in [None, "int"]:
                setattr(new, name, 0)
            elif other == "str":
                setattr(new, name, "")
            elif other == "list":
                setattr(new, name, [])
            # new.old_data[name] = copy(getattr(new, name))

        cls._every.append(new)
        return new

    @classproperty
    def random_degree(cls):
        if hasattr(cls, "custom_random_degree"):
            return cls.custom_random_degree
        else:
            return get_random_degree()

    @classproperty
    def random_difficulty(cls):
        if hasattr(cls, "custom_difficulty"):
            return cls.custom_difficulty
        else:
            return get_difficulty()

    @classproperty
    def numgroups(cls):
        return len(cls.groups)

    @classproperty
    def every(cls) -> list[Self]:
        if hasattr(cls, "_every"):
            return cls._every

        cls._every = list(get_table_objects(cls))
        return cls.every

    @classproperty
    def randomize_order(cls):
        return cls.every

    @property
    def rank(self):
        return 1

    @cached_property
    def ranked_ratio(self):
        if hasattr(self, "_ranked_ratio"):
            return self._ranked_ratio

        for o in self.every:
            o._ranked_ratio = None

        ranked = [o for o in self.ranked if o.rank >= 0]
        for i, o in enumerate(ranked):
            ratio = i / float(len(ranked) - 1)
            o._ranked_ratio = ratio

        return self.ranked_ratio

    @property
    def mutate_valid(self):
        return True

    @property
    def intershuffle_valid(self):
        return True

    @property
    def intershuffle_group(self):
        return None

    @property
    def magic_mutate_valid(self):
        return True

    @property
    def catalogue_index(self):
        return self.index

    @clached_property
    def ranked(cls):
        return sorted(cls.every, key=lambda c: (c.rank, c.signature))

    def assert_unchanged(self):
        for attr in self.old_data:
            if getattr(self, attr) != self.old_data[attr]:
                raise AssertionError(
                    '{0} {1} attribute "{2}" changed.'.format(
                        self.__class__.__name__, ("%x" % self.index), attr
                    )
                )

    def clear_cache(self):
        if hasattr(self, "_property_cache"):
            del self._property_cache

    def get_bit_similarity_score(self, other, bitmasks=None):
        if bitmasks is None:
            bitmasks = self.bit_similarity_attributes
        score = 0
        for attribute, mask in sorted(bitmasks.items()):
            a = self.old_data[attribute]
            if isinstance(other, dict):
                b = other[attribute]
            else:
                b = other.old_data[attribute]
            i = 0
            while True:
                bit = 1 << i
                if bit > mask:
                    break
                i += 1
                if not bit & mask:
                    continue
                if (a & bit) == (b & bit):
                    score += 1

        return score

    def get_similar(
        self,
        candidates=None,
        override_outsider=False,
        random_degree=None,
        allow_intershuffle_invalid=False,
        wide=False,
        presorted=False,
    ):
        if not (self.intershuffle_valid or allow_intershuffle_invalid):
            return self
        if self.rank < 0:
            return self

        if random_degree is None:
            random_degree = self.random_degree

        if candidates is None:
            candidates = [c for c in self.ranked if c.rank >= 0]
        elif not presorted:
            assert all(c.rank >= 0 for c in candidates)

        if not presorted:
            if not allow_intershuffle_invalid:
                candidates = [c for c in candidates if c.intershuffle_valid]

            candidates = sorted(set(candidates), key=lambda c: (c.rank, c.signature))
            if self.intershuffle_group is not None:
                candidates = [
                    c
                    for c in candidates
                    if c.intershuffle_group == self.intershuffle_group
                ]

        if len(candidates) <= 0:
            raise Exception("No candidates for get_similar")

        if self not in candidates:
            if override_outsider:
                index, index2 = 0, 0
                for i, c in enumerate(candidates):
                    if c.rank < self.rank:
                        index = i
                    elif c.rank <= self.rank:
                        index2 = i
                    elif c.rank > self.rank:
                        break
                if index2 and index2 > index:
                    index = random.randint(index, index2)
            else:
                raise Exception("Must manually override outsider elements.")
        else:
            override_outsider = False
            index = candidates.index(self)

        if not candidates:
            return self
        elif len(candidates) == 1:
            return candidates[0]

        if override_outsider:
            index = random.choice([index, index - 1])
            index = max(0, min(index, len(candidates) - 1))
        index = mutate_normal(
            index,
            minimum=0,
            maximum=len(candidates) - 1,
            random_degree=random_degree,
            wide=wide,
        )
        chosen = candidates[index]
        if override_outsider:
            assert chosen is not self

        return chosen

    @classmethod
    def get_similar_set(cls, current, candidates=None):
        if candidates is None:
            candidates = [c for c in cls.every if c.rank >= 0]
        candidates = sorted(set(candidates), key=lambda c: (c.rank, c.signature))
        random.shuffle(sorted(current, key=lambda c: c.index))
        chosens = []
        for c in current:
            while True:
                chosen = c.get_similar(candidates, override_outsider=True)
                assert chosen not in chosens
                chosens.append(chosen)
                candidates.remove(chosen)
                assert chosen not in candidates
                break
        assert len(chosens) == len(current)
        return chosens

    @classmethod
    def get(cls, index: int | str) -> Self:
        if isinstance(index, int):
            return GRAND_OBJECT_DICT[cls, index]
        elif isinstance(index, str):
            objs = [o for o in cls.every if index in o.name]
            if len(objs) == 1:
                return objs[0]
            elif len(objs) >= 2:
                raise Exception("Too many matching objects.")
            else:
                raise Exception("No matching objects.")
        else:
            raise Exception("Bad index.")

    @classmethod
    def get_by_pointer(cls, pointer):
        objs = [o for o in cls.every if o.pointer == pointer]
        if len(objs) == 1:
            return objs[0]
        elif len(objs) >= 2:
            raise Exception("Too many matching objects.")
        else:
            raise Exception("No matching objects.")

    @classproperty
    def groups(cls):
        returndict = {}
        for obj in cls.every:
            if obj.groupindex not in returndict:
                returndict[obj.groupindex] = []
            returndict[obj.groupindex].append(obj)
        return returndict

    @classmethod
    def getgroup(cls, index):
        return [o for o in cls.every if o.groupindex == index]

    @property
    def group(self):
        return self.getgroup(self.groupindex)

    @classmethod
    def has(cls, index):
        try:
            cls.get(index)
            return True
        except KeyError:
            return False

    def get_bit(self, bitname, old=False):
        for key, value in sorted(self.specs.bitnames.items()):
            if bitname in value:
                index = value.index(bitname)
                if old:
                    byte = self.old_data[key]
                else:
                    byte = getattr(self, key)
                bitvalue = byte & (1 << index)
                return bool(bitvalue)
        raise Exception("No bit registered under that name.")

    def set_bit(self, bitname, bitvalue):
        bitvalue = 1 if bitvalue else 0
        for key, value in self.specs.bitnames.items():
            if bitname in value:
                index = value.index(bitname)
                assert index <= 7
                byte = getattr(self, key)
                if bitvalue:
                    byte = byte | (1 << index)
                else:
                    byte = byte & (0xFF ^ (1 << index))
                setattr(self, key, byte)
                return
        raise Exception("No bit registered under that name.")

    @property
    def display_name(self):
        if not hasattr(self, "name"):
            self.name = "%x" % self.index
        if isinstance(self.name, int):
            return "%x" % self.name
        return "".join([c for c in self.name if c in string.printable])

    @property
    def verification_signature(self):
        return self.get_verification_signature(old_data=False)

    @property
    def old_verification_signature(self):
        return self.get_verification_signature(old_data=True)

    def get_verification_signature(self, old_data=False):
        labels = sorted([a for (a, b, c) in self.specs.attributes if c not in ["str"]])
        if old_data:
            data = str([(label, self.old_data[label]) for label in labels])
        else:
            data = str([(label, getattr(self, label)) for label in labels])

        datahash = md5(data).hexdigest()
        signature = "{0}:{1:0>4}:{2}".format(
            self.__class__.__name__, ("%x" % self.index), datahash
        )
        return signature

    @property
    def description(self):
        classname = self.__class__.__name__
        pointer = "%x" % self.pointer if self.pointer else "None"
        desc = "{0} {1:02x} {2} {3}".format(
            classname, self.index, pointer, self.display_name
        )
        return desc

    @property
    def pretty_description(self):
        if hasattr(self, "name"):
            s = "{0} {1:0>3X} {2}\n".format(
                self.__class__.__name__, self.index, self.name
            )
        else:
            s = "{0} {1:0>3X}\n".format(self.__class__.__name__, self.index)
        for attr, size, other in self.specs.attributes:
            value = getattr(self, attr)
            if isinstance(value, int):
                s += ("  {0}: {1:0>%sx}\n" % (size * 2)).format(attr, value)
            elif isinstance(value, bytes):
                s += "  {0}: {1}\n".format(attr, value)
            elif isinstance(value, list):
                if isinstance(size, str) and "x" in size:
                    length, width = map(int, size.split("x"))
                else:
                    width = 1
                value = " ".join([("{0:0>%sx}" % (width * 2)).format(v) for v in value])
                s += "  {0}: {1}\n".format(attr, value)
            else:
                s += "  {0}: ???\n".format(attr)
        return s.strip()

    @property
    def long_description(self):
        s = []
        for attr in sorted(dir(self)):
            if attr.startswith("_"):
                continue

            if attr in ["specs", "catalogue"]:
                continue

            if hasattr(self.__class__, attr):
                class_attr = getattr(self.__class__, attr)
                if isinstance(class_attr, property) or hasattr(class_attr, "__call__"):
                    continue

            try:
                value = getattr(self, attr)
            except AttributeError:
                continue

            if isinstance(value, dict):
                continue

            if isinstance(value, list):
                if value and not isinstance(value[0], int):
                    continue
                value = " ".join(["%x" % v for v in value])

            if isinstance(value, int):
                value = "%x" % value

            s.append((attr, "%s" % str(value)))

        s = ", ".join(["%s: %s" % (a, b) for (a, b) in s])
        s = "%x - %s" % (self.index, s)
        return s

    @classproperty
    def catalogue(self):
        logs = []
        for obj in sorted(self.every, key=lambda o: o.catalogue_index):
            logs.append(obj.log.strip())

        if any(["\n" in log for log in logs]):
            return "\n\n".join(logs)
        else:
            return "\n".join(logs)

    @property
    def log(self):
        return str(self)

    def __repr__(self):
        return self.description

    def get_variable_specsattrs(self):
        specsattrs = [
            (name, self.variable_size, other)
            for (name, size, other) in self.specs.attributes
            if size == 0
        ]
        if not specsattrs:
            raise ValueError("No valid specs attributes.")
        elif len(specsattrs) >= 2:
            raise ValueError("Too many specs attributes.")
        return specsattrs

    def read_data(self, filename=None, pointer=None):
        if pointer is None:
            pointer = self.pointer
        if filename is None:
            filename = self.filename
        if pointer is None or filename is None:
            return

        if self.variable_size is not None:
            specsattrs = self.get_variable_specsattrs()
        else:
            specsattrs = self.specs.attributes

        self.old_data = {}
        f = get_open_file(filename)
        f.seek(pointer)
        for name, size, other in specsattrs:
            if other in [None, "int"]:
                value = read_multi(f, length=size)
            elif other == "str":
                value = f.read(size)
            elif other == "list":
                if not isinstance(size, int):
                    number, numbytes = size.split("x")
                    number, numbytes = int(number), int(numbytes)
                else:
                    number, numbytes = size, 1
                value = []
                for i in range(number):
                    value.append(read_multi(f, numbytes))
            self.old_data[name] = copy(value)
            setattr(self, name, value)

    def copy_data(self, another):
        for name, _, _ in self.specs.attributes:
            value = getattr(another, name)
            setattr(self, name, value)

    def write_data(self, filename: str | None=None, pointer: int | None=None, syncing: bool=False):
        if pointer is None:
            pointer = self.pointer
        if filename is None:
            filename = self.filename
        if pointer is None or filename is None:
            return

        if (
            not syncing
            and hasattr(self.specs, "syncpointers")
            and self.specs.syncpointers
        ):
            for p in self.specs.syncpointers:
                offset = p - self.specs.pointer
                new_pointer = self.pointer + offset
                self.write_data(filename=filename, pointer=new_pointer, syncing=True)
            return

        if self.variable_size is not None:
            # doesn't seem to work properly
            raise NotImplementedError
            specsattrs = self.get_variable_specsattrs()
        else:
            specsattrs = self.specs.attributes

        f = get_open_file(filename)
        for name, size, other in specsattrs:
            value = getattr(self, name)
            if other in [None, "int"]:
                assert value >= 0
                f.seek(pointer)
                write_multi(f, value, length=size)
                pointer += size
            elif other == "str":
                assert len(value) == size
                f.seek(pointer)
                f.write(value)
                pointer += size
            elif other == "list":
                if not isinstance(size, int):
                    number, numbytes = size.split("x")
                    number, numbytes = int(number), int(numbytes)
                else:
                    number, numbytes = size, 1
                assert len(value) == number
                for v in value:
                    f.seek(pointer)
                    write_multi(f, v, length=numbytes)
                    pointer += numbytes
        return pointer

    @classmethod
    def write_all(cls, filename):
        if cls.specs.pointedpoint1 or not (
            cls.specs.grouped or cls.specs.pointed or cls.specs.delimit
        ):
            for o in cls.every:
                o.write_data()
        elif cls.specs.grouped:
            pointer = cls.specs.pointer
            f = get_open_file(filename)
            for i in range(cls.numgroups):
                objs = [o for o in cls.every if o.groupindex == i]
                f.seek(pointer)
                if cls.specs.groupednum is None:
                    f.write(chr(len(objs)))
                    pointer += 1
                for o in objs:
                    pointer = o.write_data(None, pointer)
        elif cls.specs.pointed and cls.specs.delimit:
            pointer = cls.specs.pointedpointer
            f = get_open_file(filename)
            for i in range(cls.specs.count):
                objs = [o for o in cls.every if o.groupindex == i]
                if not objs:
                    continue
                f.seek(cls.specs.pointer + (cls.specs.pointedsize * i))
                write_multi(
                    f, pointer - cls.specs.pointedpointer, length=cls.specs.pointedsize
                )
                f.seek(pointer)
                for o in objs:
                    pointer = o.write_data(None, pointer)
                f.seek(pointer)
                f.write(bytes([cls.specs.delimitval]))
                pointer += 1
            if pointer == cls.specs.pointedpointer:
                raise Exception("No objects in pointdelimit data.")
            nullpointer = pointer - 1
            for i in range(cls.specs.count):
                objs = [o for o in cls.every if o.groupindex == i]
                if objs:
                    continue
                f.seek(cls.specs.pointer + (cls.specs.pointedsize * i))
                write_multi(
                    f,
                    nullpointer - cls.specs.pointedpointer,
                    length=cls.specs.pointedsize,
                )
        elif cls.specs.pointed:
            pointer = cls.specs.pointer
            size = cls.specs.pointedsize
            f = get_open_file(filename)
            first_pointer = min(
                [
                    o.pointer
                    for o in cls.every
                    if o is not None and o.pointer is not None
                ]
            )
            pointedpointer = max(first_pointer, pointer + (cls.specs.count * size))
            mask = (2 ** (8 * size)) - 1
            for i in range(cls.specs.count):
                # masked = pointedpointer & mask
                masked = (pointedpointer - cls.specs.pointedpointer) & mask
                objs = [o for o in cls.every if o.groupindex == i]
                if hasattr(cls, "groupsort"):
                    objs = cls.groupsort(objs)
                for o in objs:
                    pointedpointer = o.write_data(None, pointedpointer)
                f.seek(pointer + (i * size))
                write_multi(f, masked, length=size)
        elif cls.specs.delimit:
            f = get_open_file(filename)
            pointer = cls.specs.pointer
            for i in range(cls.specs.count):
                objs = cls.getgroup(i)
                if hasattr(cls, "groupsort"):
                    objs = cls.groupsort(objs)
                for o in objs:
                    pointer = o.write_data(None, pointer)
                f.seek(pointer)
                f.write(chr(cls.specs.delimitval))
                pointer += 1

    def preprocess(self):
        return

    def preclean(self):
        return

    def cleanup(self):
        return

    @classmethod
    def full_preclean(cls):
        if hasattr(cls, "after_order"):
            for cls2 in cls.after_order:
                if not (hasattr(cls2, "precleaned") and cls2.precleaned):
                    raise Exception("Preclean order violated: %s %s" % (cls, cls2))
        for o in cls.every:
            o.reseed("preclean")
            o.preclean()
        cls.precleaned = True

    @classmethod
    def full_cleanup(cls):
        if hasattr(cls, "after_order"):
            for cls2 in cls.after_order:
                if not (hasattr(cls2, "cleaned") and cls2.cleaned):
                    raise Exception("Clean order violated: %s %s" % (cls, cls2))
        for o in cls.every:
            o.reseed("cleanup")
            o.cleanup()
        cls.cleaned = True

    @cached_property
    def signature(self):
        filename = "/".join(self.filename.split(path.sep))
        identifier = "%s%s" % (filename, self.pointer)
        left = "%s%s%s" % (get_seed(), identifier, self.__class__.__name__)
        right = "%s%s" % (self.index, get_seed())
        left = md5(left.encode("ascii")).hexdigest()
        right = md5(right.encode("ascii")).hexdigest()
        return "%s%s%s%x" % (left, identifier, right, self.index)

    def reseed(self, salt=""):
        s = "%s%s%s%s" % (get_seed(), self.index, salt, self.__class__.__name__)
        value = int(md5(s.encode("ascii")).hexdigest(), 0x10)
        random.seed(value)

    @classmethod
    def class_reseed(cls, salt=""):
        obj = cls.every[0]
        obj.reseed(salt="cls" + salt)

    @classmethod
    def preprocess_all(cls):
        for o in cls.every:
            o.reseed(salt="preprocess")
            o.preprocess()

    @classmethod
    def full_randomize(cls):
        if hasattr(cls, "after_order"):
            for cls2 in cls.after_order:
                if not (
                    hasattr(cls2, "randomize_step_finished")
                    and cls2.randomize_step_finished
                ):
                    raise Exception("Randomize order violated: %s %s" % (cls, cls2))

        cls.class_reseed("group")
        cls.groupshuffle()
        cls.class_reseed("inter")
        cls.intershuffle()
        cls.class_reseed("randsel")
        cls.randomselect_all()
        cls.class_reseed("full")
        cls.shuffle_all()
        cls.randomize_all()
        cls.mutate_all()
        cls.randomized = True

    @classmethod
    def mutate_all(cls):
        for o in cls.randomize_order:
            if hasattr(o, "mutated") and o.mutated:
                continue
            o.reseed(salt="mut")
            if o.mutate_valid:
                o.mutate()
            o.mutate_bits()
            if o.magic_mutate_valid:
                o.magic_mutate_bits()
            o.mutated = True

    @classmethod
    def randomize_all(cls):
        for o in cls.randomize_order:
            if hasattr(o, "randomized") and o.randomized:
                continue
            o.reseed(salt="ran")
            o.randomize()
            o.randomized = True

    @classmethod
    def shuffle_all(cls):
        for o in cls.randomize_order:
            if hasattr(o, "shuffled") and o.shuffled:
                continue
            o.reseed(salt="shu")
            o.shuffle()
            o.shuffled = True

    def mutate(self):
        if not hasattr(self, "mutate_attributes"):
            return

        if not self.mutate_valid:
            return

        self.reseed(salt="mut")
        for attribute in sorted(self.mutate_attributes):
            mutatt = getattr(self, attribute)
            if not isinstance(mutatt, list):
                mutatt = [mutatt]
            newatt = []

            if isinstance(self.mutate_attributes[attribute], type):
                tob = self.mutate_attributes[attribute]
                for ma in mutatt:
                    tob = tob.get(ma)
                    tob = tob.get_similar()
                    newatt.append(tob.index)
            else:
                minmax = self.mutate_attributes[attribute]
                if type(minmax) is tuple:
                    minimum, maximum = minmax
                else:
                    values = [
                        o.old_data[attribute] for o in self.every if o.mutate_valid
                    ]
                    if isinstance(values[0], list):
                        values = [v2 for v1 in values for v2 in v1]
                    minimum, maximum = min(values), max(values)
                    self.mutate_attributes[attribute] = (minimum, maximum)

                for ma in mutatt:
                    if ma < minimum or ma > maximum:
                        newatt.append(ma)
                        continue
                    ma = mutate_normal(
                        ma, minimum, maximum, random_degree=self.random_degree
                    )
                    newatt.append(ma)

            if not isinstance(self.old_data[attribute], list):
                assert len(newatt) == 1
                newatt = newatt[0]
            setattr(self, attribute, newatt)

    def mutate_bits(self):
        if not hasattr(self, "mutate_bit_attributes"):
            return

        for attribute in sorted(self.mutate_bit_attributes):
            chance = self.mutate_bit_attributes[attribute]
            if random.random() <= chance:
                value = self.get_bit(attribute)
                self.set_bit(attribute, not value)

    def magic_mutate_bits(self, random_degree=None):
        if (
            self.rank < 0
            or not hasattr(self, "magic_mutate_bit_attributes")
            or not self.magic_mutate_valid
        ):
            return

        if random_degree is None:
            random_degree = self.random_degree

        base_candidates = [
            o for o in self.every if o.magic_mutate_valid and o.rank >= 0
        ]

        if not hasattr(self.__class__, "_candidates_dict"):
            self.__class__._candidates_dict = {}

        self.reseed(salt="magmutbit")
        for attributes in sorted(self.magic_mutate_bit_attributes):
            masks = self.magic_mutate_bit_attributes[attributes]
            if isinstance(attributes, str):
                del self.magic_mutate_bit_attributes[attributes]
                attributes = tuple([attributes])
            if masks is None:
                masks = tuple([None for a in attributes])
            if isinstance(masks, int):
                masks = (masks,)
            bitmasks = dict(zip(attributes, masks))
            for attribute, mask in bitmasks.items():
                if mask is None:
                    mask = 0
                    for c in base_candidates:
                        mask |= getattr(c, attribute)
                    bitmasks[attribute] = mask
            masks = tuple([bitmasks[a] for a in attributes])
            self.magic_mutate_bit_attributes[attributes] = masks

            def obj_to_dict(o):
                return dict([(a, getattr(o, a)) for a in attributes])

            wildcard = [random.randint(0, m << 1) & m for m in masks]
            wildcard = []
            for attribute, mask in bitmasks.items():
                value = random.randint(0, mask << 1) & mask
                while True:
                    if not value:
                        break
                    v = random.randint(0, value) & mask
                    if not v & value:
                        if bin(v).count("1") <= bin(value).count("1"):
                            value = v
                        if random.choice([True, False]):
                            break
                    else:
                        value &= v
                value = self.old_data[attribute] ^ value
                wildcard.append((attribute, value))

            if attributes not in self._candidates_dict:
                candidates = []
                for o in base_candidates:
                    candidates.append(tuple([getattr(o, a) for a in attributes]))
                counted_candidates = Counter(candidates)
                candidates = []
                for values in sorted(counted_candidates):
                    valdict = dict(zip(attributes, values))
                    frequency = counted_candidates[values]
                    frequency = int(round(frequency ** (1 - (random_degree**0.5))))
                    candidates.extend([valdict] * frequency)
                self._candidates_dict[attributes] = candidates

            candidates = list(self._candidates_dict[attributes])
            candidates += [dict(wildcard)]
            if obj_to_dict(self) not in candidates:
                candidates += [obj_to_dict(self)]
            candidates = sorted(
                candidates,
                key=lambda o: (
                    self.get_bit_similarity_score(o, bitmasks=bitmasks),
                    o.signature if hasattr(o, "signature") else -1,
                    o.index if hasattr(o, "index") else -1,
                ),
                reverse=True,
            )
            index = candidates.index(obj_to_dict(self))
            max_index = len(candidates) - 1
            index = mutate_normal(
                index, 0, max_index, random_degree=random_degree, wide=True
            )
            chosen = candidates[index]
            if chosen is self:
                continue
            if not isinstance(chosen, dict):
                chosen = chosen.old_data
            for attribute, mask in sorted(bitmasks.items()):
                diffmask = getattr(self, attribute) ^ chosen[attribute]
                diffmask &= mask
                if not diffmask:
                    continue
                i = 0
                while True:
                    bit = 1 << i
                    i += 1
                    if bit > (diffmask | mask):
                        break

                    if (
                        bit & mask
                        and not bit & diffmask
                        and random.random() < random_degree**6
                    ):
                        diffmask |= bit

                    if bit & diffmask:
                        if random.random() < ((random_degree**0.5) / 2.0):
                            continue
                        else:
                            diffmask ^= bit
                setattr(self, attribute, getattr(self, attribute) ^ diffmask)

    def randomize(self):
        if not hasattr(self, "randomize_attributes"):
            return
        if not self.intershuffle_valid:
            return

        self.reseed(salt="ran")
        candidates = [c for c in self.every if c.rank >= 0 and c.intershuffle_valid]
        if self.intershuffle_group is not None:
            candidates = [
                c for c in candidates if c.intershuffle_group == self.intershuffle_group
            ]
        for attribute in sorted(self.randomize_attributes):
            chosen = random.choice(candidates)
            setattr(self, attribute, chosen.old_data[attribute])

    def shuffle(self):
        if not hasattr(self, "shuffle_attributes"):
            return

        self.reseed(salt="shu")
        for attributes in sorted(self.shuffle_attributes):
            if len(attributes) == 1:
                attribute = attributes[0]
                value = sorted(getattr(self, attribute))
                random.shuffle(value)
                setattr(self, attribute, value)
                continue
            values = [getattr(self, attribute) for attribute in attributes]
            random.shuffle(values)
            for attribute, value in zip(attributes, values):
                setattr(self, attribute, value)

    def randomselect(self, candidates=None):
        if not hasattr(self, "randomselect_attributes"):
            return

        self.reseed("randsel")
        if candidates is None:
            candidates = [c for c in self.every if c.intershuffle_valid]
        if self.intershuffle_group is not None:
            candidates = [
                c for c in candidates if c.intershuffle_group == self.intershuffle_group
            ]

        if len(set([o.rank for o in candidates])) <= 1:
            hard_shuffle = True
        else:
            hard_shuffle = False

        for attributes in self.randomselect_attributes:
            if hard_shuffle:
                other = random.choice(candidates)
            else:
                other = self.get_similar(candidates)
            if isinstance(attributes, str):
                attributes = [attributes]
            for attribute in attributes:
                setattr(self, attribute, other.old_data[attribute])
        self.random_selected = True

    @classmethod
    def intershuffle(cls, candidates=None, random_degree=None):
        if not hasattr(cls, "intershuffle_attributes"):
            return

        if random_degree is None:
            random_degree = cls.random_degree

        if candidates is None:
            candidates = list(cls.every)

        candidates = [o for o in candidates if o.rank >= 0 and o.intershuffle_valid]

        cls.class_reseed("inter")
        hard_shuffle = False
        if len(set([o.rank for o in candidates])) == 1 or all(
            [o.rank == o.index for o in candidates]
        ):
            hard_shuffle = True

        for attributes in cls.intershuffle_attributes:
            if hard_shuffle:
                shuffled = list(candidates)
                random.shuffle(shuffled)
            else:
                candidates = sorted(candidates, key=lambda c: (c.rank, c.signature))
                shuffled = shuffle_normal(candidates, random_degree=random_degree)

            if isinstance(attributes, str):
                attributes = [attributes]

            for attribute in attributes:
                swaps = []
                for a, b in zip(candidates, shuffled):
                    aval, bval = getattr(a, attribute), getattr(b, attribute)
                    swaps.append(bval)
                for a, bval in zip(candidates, swaps):
                    setattr(a, attribute, bval)

    @classmethod
    def randomselect_all(cls, candidates=None):
        if candidates is None:
            candidates = list(cls.randomize_order)
        candidates = [o for o in candidates if o.rank >= 0 and o.intershuffle_valid]

        for o in candidates:
            o.randomselect(candidates=candidates)
            o.random_selected = True

    @classmethod
    def groupshuffle(cls):
        if not hasattr(cls, "groupshuffle_enabled") or not cls.groupshuffle_enabled:
            return

        cls.class_reseed("group")
        shuffled = range(cls.numgroups)
        random.shuffle(shuffled)
        swapdict = {}
        for a, b in zip(range(cls.numgroups), shuffled):
            a = cls.getgroup(a)
            b = cls.getgroup(b)
            for a1, b1 in zip(a, b):
                swapdict[a1] = (b1.groupindex, b1.index, b1.pointer)

        for o in cls.every:
            groupindex, index, pointer = swapdict[o]
            o.groupindex = groupindex
            o.index = index
            o.pointer = pointer


class FileEntry:
    target_sector: int
    files: list[Self] | None

    STRUCT = [
        ("_size", 1),
        ("num_ear", 1),
        ("target_sector", 4),
        ("target_sector_reverse", 4),
        ("filesize", 4),
        ("filesize_reverse", 4),
        ("year", 1),
        ("month", 1),
        ("day", 1),
        ("hour", 1),
        ("minute", 1),
        ("second", 1),
        ("tz_offset", 1),
        ("flags", 1),
        ("interleaved_unit_size", 1),
        ("interleaved_gap_size", 1),
        ("one", 2),
        ("unk3", 2),
        ("name_length", 1),
        ("name", None),
        ("pattern", 14),
    ]

    def __init__(self, imgname: str, pointer: int, dirname: str, initial_sector: int):
        self.imgname = imgname
        self.pointer = pointer
        self.dirname = dirname
        self.initial_sector = initial_sector

    def __repr__(self):
        return self.path

    @property
    def printable_name(self):
        # return any([c in printable for c in self.name])
        # print(printable, self.name)
        return all([c in printable for c in self.name])

    @property
    def start_sector(self):
        return self.target_sector

    @property
    def end_sector(self):
        return self.start_sector + self.num_sectors

    @property
    def num_sectors(self):
        num_sectors = self.filesize / 0x800
        if self.filesize > num_sectors * 0x800:
            num_sectors += 1
        return max(num_sectors, 1)

    @property
    def hidden(self):
        return self.flags & 1

    @property
    def is_directory(self):
        return self.flags & 0x2

    @cached_property
    def path(self):
        return path.join(self.dirname, self.name)

    @classmethod
    def get_cached_file_from_sectors(self, imgname, initial_sector):
        if not hasattr(FileEntry, "_file_cache"):
            FileEntry._file_cache = {}

        key = (imgname, initial_sector)
        if key in FileEntry._file_cache:
            return FileEntry._file_cache[key]

        tempname = "_temp.{0:x}.bin".format(initial_sector)
        tempname = path.join(SANDBOX_PATH, tempname)
        f = file_from_sectors(imgname, initial_sector, tempname)
        FileEntry._file_cache[key] = f

        return FileEntry.get_cached_file_from_sectors(imgname, initial_sector)

    @classmethod
    def write_cached_files(self):
        if not hasattr(FileEntry, "_file_cache"):
            return

        for (imgname, initial_sector), f in sorted(FileEntry._file_cache.items()):
            fname = f.name
            f.close()
            write_data_to_sectors(imgname, initial_sector, datafile=fname)

    @property
    def size(self):
        size = 0
        for attr, length in self.STRUCT:
            if length is not None:
                size += length
            else:
                assert attr == "name"
                size += len(self.name)
                if not len(self.name) % 2:
                    size += 1
        return size

    def validate(self):
        assert self.num_ear == 0
        assert not self.size % 2
        assert not self.flags & 0xFC
        assert not self.interleaved_unit_size or self.interleaved_gap_size
        assert self.one == 1
        if self.is_directory:
            assert self.pattern == DIRECTORY_PATTERN
        else:
            assert self.name[-2:] == ";1"
        if hasattr(self, "_size"):
            assert self.size == self._size

    def clone_entry(self, other):
        for attr, length in self.STRUCT:
            setattr(self, attr, getattr(other, attr))

    def update_file_entry(self):
        self.validate()

        self._size = self.size

        f = self.get_cached_file_from_sectors(self.imgname, self.initial_sector)

        f.seek(self.pointer)
        for attr, length in self.STRUCT:
            if attr == "target_sector_reverse":
                f.write(self.target_sector.to_bytes(length=4, byteorder="big"))
            elif attr == "filesize_reverse":
                f.write(self.filesize.to_bytes(length=4, byteorder="big"))
            elif attr == "name_length":
                name_length = len(self.name)
                f.write(bytes([name_length]))
                self.name_length = name_length
            elif attr == "name":
                f.write(self.name.encode("ascii"))
                if not self.name_length % 2:
                    f.write(b"\x00")
            elif attr == "pattern":
                f.write(self.pattern)
            else:
                value = getattr(self, attr)
                f.write(value.to_bytes(length=length, byteorder="little"))

        assert f.tell() == self.pointer + self.size

    def read_file_entry(self):
        self.old_data = {}

        f = self.get_cached_file_from_sectors(self.imgname, self.initial_sector)

        f.seek(self.pointer)
        for attr, length in self.STRUCT:
            if length == None and attr == "name":
                length = self.name_length
                self.name = f.read(length).decode("ascii")
                if not self.name_length % 2:
                    p = f.read(1)
                    assert p == b"\x00"

            elif attr == "pattern":
                self.pattern = f.read(length)

            elif attr == "_size":
                peek = f.read(1)
                if len(peek) == 0:
                    raise EOFError
                self._size = ord(peek)
                if self._size == 0:
                    raise FileEntryReadException

            else:
                value = int.from_bytes(f.read(length), byteorder="little")
                setattr(self, attr, value)

            self.old_data[attr] = getattr(self, attr)

        self.validate()
        assert f.tell() == self.pointer + self.size

    def write_data(self, filepath=None):
        if self.is_directory or not self.printable_name or not self.filesize:
            return
        if filepath is None:
            filepath = path.join(self.dirname, self.name)
            assert filepath.endswith(";1")
            filepath = filepath[:-2]
            if not path.exists(self.dirname):
                makedirs(self.dirname)

        f = file_from_sectors(self.imgname, self.target_sector, filepath)
        f.close()

        written_size = stat(filepath).st_size
        assert not written_size % 0x800
        start_byte = self.target_sector * 0x800
        interval = (start_byte, start_byte + written_size)
        start, finish = interval
        if not hasattr(FileEntry, "WRITTEN_INTERVALS"):
            FileEntry.WRITTEN_INTERVALS = {}

        assert filepath not in self.WRITTEN_INTERVALS
        errmsg = "WARNING: {0} overlaps {1} at {2:x}. Truncating {1}."
        for donepath in sorted(self.WRITTEN_INTERVALS):
            donestart, donefinish = self.WRITTEN_INTERVALS[donepath]
            if start <= donestart < finish:
                # truncate this file
                newfinish = donestart
                newsize = newfinish - start
                print(errmsg.format(donepath, filepath, newsize))
                with open(filepath, "r+b") as f:
                    f.truncate(newsize)
                finish = newfinish
            if start < donefinish <= finish:
                # truncate the other file
                newfinish = start
                newsize = newfinish - donestart
                print(errmsg.format(filepath, donepath, newsize))
                with open(donepath, "r+b") as f:
                    f.truncate(newsize)
                assert newfinish >= donestart
                self.WRITTEN_INTERVALS[donepath] = (donestart, newfinish)
        assert finish >= start
        self.WRITTEN_INTERVALS[filepath] = (start, finish)


SYNC_PATTERN = bytes([0] + ([0xFF] * 10) + [0])


def read_directory(
    imgname: str,
    dirname: str,
    sector_index: int | None = None,
    minute: int | None = None,
    second: int | None = None,
    sector: int | None = None,
):
    if sector_index is None:
        assert minute is not None
        assert second is not None
        assert sector is not None
        sector_index = (minute * 60 * 75) + ((second - 2) * 75) + sector
    pointer = sector_index * 0x930
    with open(imgname, "r+b") as f:
        f.seek(pointer)
        temp = f.read(12)
        # print(hex(pointer), temp, SYNC_PATTERN)
        assert temp == SYNC_PATTERN
        f.seek(pointer + 15)
        mode = ord(f.read(1))
        assert mode == 2

    pointer = 0
    fes: list[FileEntry] = []
    while True:
        try:
            fe = FileEntry(imgname, pointer, dirname, sector_index)
            fe.read_file_entry()
            pointer = fe.pointer + fe.size
            fes.append(fe)
        except FileEntryReadException:
            pointer = ((pointer // 0x800) + 1) * 0x800
        except EOFError:
            break

    for fe in fes:
        fe.files = None
        if fe.is_directory and fe.printable_name and sector_index != fe.target_sector:
            subfes = read_directory(
                imgname, path.join(dirname, fe.name), sector_index=fe.target_sector
            )
            fe.files = subfes

    return fes


EDC_crctable = [
    0x00000000, 0x90910101, 0x91210201, 0x01B00300,
    0x92410401, 0x02D00500, 0x03600600, 0x93F10701,
    0x94810801, 0x04100900, 0x05A00A00, 0x95310B01,
    0x06C00C00, 0x96510D01, 0x97E10E01, 0x07700F00,
    0x99011001, 0x09901100, 0x08201200, 0x98B11301,
    0x0B401400, 0x9BD11501, 0x9A611601, 0x0AF01700,
    0x0D801800, 0x9D111901, 0x9CA11A01, 0x0C301B00,
    0x9FC11C01, 0x0F501D00, 0x0EE01E00, 0x9E711F01,
    0x82012001, 0x12902100, 0x13202200, 0x83B12301,
    0x10402400, 0x80D12501, 0x81612601, 0x11F02700,
    0x16802800, 0x86112901, 0x87A12A01, 0x17302B00,
    0x84C12C01, 0x14502D00, 0x15E02E00, 0x85712F01,
    0x1B003000, 0x8B913101, 0x8A213201, 0x1AB03300,
    0x89413401, 0x19D03500, 0x18603600, 0x88F13701,
    0x8F813801, 0x1F103900, 0x1EA03A00, 0x8E313B01,
    0x1DC03C00, 0x8D513D01, 0x8CE13E01, 0x1C703F00,
    0xB4014001, 0x24904100, 0x25204200, 0xB5B14301,
    0x26404400, 0xB6D14501, 0xB7614601, 0x27F04700,
    0x20804800, 0xB0114901, 0xB1A14A01, 0x21304B00,
    0xB2C14C01, 0x22504D00, 0x23E04E00, 0xB3714F01,
    0x2D005000, 0xBD915101, 0xBC215201, 0x2CB05300,
    0xBF415401, 0x2FD05500, 0x2E605600, 0xBEF15701,
    0xB9815801, 0x29105900, 0x28A05A00, 0xB8315B01,
    0x2BC05C00, 0xBB515D01, 0xBAE15E01, 0x2A705F00,
    0x36006000, 0xA6916101, 0xA7216201, 0x37B06300,
    0xA4416401, 0x34D06500, 0x35606600, 0xA5F16701,
    0xA2816801, 0x32106900, 0x33A06A00, 0xA3316B01,
    0x30C06C00, 0xA0516D01, 0xA1E16E01, 0x31706F00,
    0xAF017001, 0x3F907100, 0x3E207200, 0xAEB17301,
    0x3D407400, 0xADD17501, 0xAC617601, 0x3CF07700,
    0x3B807800, 0xAB117901, 0xAAA17A01, 0x3A307B00,
    0xA9C17C01, 0x39507D00, 0x38E07E00, 0xA8717F01,
    0xD8018001, 0x48908100, 0x49208200, 0xD9B18301,
    0x4A408400, 0xDAD18501, 0xDB618601, 0x4BF08700,
    0x4C808800, 0xDC118901, 0xDDA18A01, 0x4D308B00,
    0xDEC18C01, 0x4E508D00, 0x4FE08E00, 0xDF718F01,
    0x41009000, 0xD1919101, 0xD0219201, 0x40B09300,
    0xD3419401, 0x43D09500, 0x42609600, 0xD2F19701,
    0xD5819801, 0x45109900, 0x44A09A00, 0xD4319B01,
    0x47C09C00, 0xD7519D01, 0xD6E19E01, 0x46709F00,
    0x5A00A000, 0xCA91A101, 0xCB21A201, 0x5BB0A300,
    0xC841A401, 0x58D0A500, 0x5960A600, 0xC9F1A701,
    0xCE81A801, 0x5E10A900, 0x5FA0AA00, 0xCF31AB01,
    0x5CC0AC00, 0xCC51AD01, 0xCDE1AE01, 0x5D70AF00,
    0xC301B001, 0x5390B100, 0x5220B200, 0xC2B1B301,
    0x5140B400, 0xC1D1B501, 0xC061B601, 0x50F0B700,
    0x5780B800, 0xC711B901, 0xC6A1BA01, 0x5630BB00,
    0xC5C1BC01, 0x5550BD00, 0x54E0BE00, 0xC471BF01,
    0x6C00C000, 0xFC91C101, 0xFD21C201, 0x6DB0C300,
    0xFE41C401, 0x6ED0C500, 0x6F60C600, 0xFFF1C701,
    0xF881C801, 0x6810C900, 0x69A0CA00, 0xF931CB01,
    0x6AC0CC00, 0xFA51CD01, 0xFBE1CE01, 0x6B70CF00,
    0xF501D001, 0x6590D100, 0x6420D200, 0xF4B1D301,
    0x6740D400, 0xF7D1D501, 0xF661D601, 0x66F0D700,
    0x6180D800, 0xF111D901, 0xF0A1DA01, 0x6030DB00,
    0xF3C1DC01, 0x6350DD00, 0x62E0DE00, 0xF271DF01,
    0xEE01E001, 0x7E90E100, 0x7F20E200, 0xEFB1E301,
    0x7C40E400, 0xECD1E501, 0xED61E601, 0x7DF0E700,
    0x7A80E800, 0xEA11E901, 0xEBA1EA01, 0x7B30EB00,
    0xE8C1EC01, 0x7850ED00, 0x79E0EE00, 0xE971EF01,
    0x7700F000, 0xE791F101, 0xE621F201, 0x76B0F300,
    0xE541F401, 0x75D0F500, 0x7460F600, 0xE4F1F701,
    0xE381F801, 0x7310F900, 0x72A0FA00, 0xE231FB01,
    0x71C0FC00, 0xE151FD01, 0xE0E1FE01, 0x7070FF00,
    ]

L2sq = [
    [    0, 44719, 16707, 61420, 33414, 11305, 50117, 28010,
      6417, 47038, 22610, 63229, 39831, 13624, 56020, 29819,
     12834, 40077, 29537, 56782, 45220,  7691, 61927, 24392,
     11059, 34204, 27248, 50399, 43445,  1818, 59638, 18009,
     25668, 51947,  9479, 35752, 59074, 18541, 42881,  2350,
     32085, 54266, 15382, 37561, 65491, 20860, 48784,  4159,
     22118, 63689,  5925, 47498, 54496, 31311, 38307, 15116,
     20343, 57816,  3636, 41115, 52721, 25438, 36018,  8733,
     51336, 26151, 35275, 10084, 18958, 58529,  2893, 42466,
     53657, 32566, 37082, 15989, 21279, 64944,  4700, 48371,
     64170, 21509, 48105,  5446, 30764, 54915, 14703, 38848,
     58299, 19732, 41720,  3159, 24893, 53138,  8318, 36561,
     44236,   611, 60815, 17184, 11850, 32997, 28425, 49574,
     46557,  7026, 62622, 23089, 14171, 39412, 30232, 55479,
     40686, 12353, 57261, 28930,  7272, 45767, 23851, 62340,
     34815, 10576, 50876, 26643,  1401, 43990, 17466, 60053,
     36109,  9122, 52302, 25313,  3979, 41252, 20168, 57447,
     37916, 15027, 54623, 31728,  5786, 47157, 22489, 63862,
     48943,  4480, 65132, 20675, 15785, 37638, 31978, 53829,
     42558,  2193, 59261, 18898,  9400, 35351, 26107, 52052,
     59721, 18406, 43018,  1701, 27599, 50528, 10892, 33827,
     61528, 24311, 45339,  8116, 29406, 56433, 13213, 40242,
     56171, 30148, 39464, 13447, 23021, 63298,  6318, 46593,
     49786, 27861, 33593, 11670, 16636, 61011,   447, 44816,
     17797, 60202,  1222, 43625, 50947, 27052, 34368, 10479,
     23700, 62011,  7639, 45944, 56850, 28861, 40785, 12798,
     30631, 55560, 14052, 38987, 62753, 23438, 46178,  6861,
     28342, 49177, 12277, 33114, 60464, 17055, 44403,   988,
      8641, 36718, 24706, 52781, 41799,  3560, 57860, 19627,
     14544, 38527, 31123, 55100, 47702,  5369, 64277, 21946,
      5091, 48460, 21152, 64527, 37221, 16330, 53286, 32393,
      2802, 42077, 19377, 58654, 34932,  9947, 51511, 26520],
    [    0, 55768, 44973, 30325, 17223, 39583, 60650, 13618,
     34446, 24406, 10531, 61691, 50633,  7185, 27236, 46012,
      4353, 51417, 48812, 26484, 21062, 35742, 65003,  9267,
     38799, 20055, 14370, 57850, 54472,  3344, 31589, 41661,
      8706, 64474, 36271, 21623, 24901, 47261, 52968,  5936,
     42124, 32084,  2849, 54009, 59339, 15891, 18534, 37310,
     13059, 60123, 40110, 17782, 28740, 43420, 57321,  1585,
     46477, 27733,  6688, 50168, 63178, 12050, 22887, 32959,
     17412, 40412, 60329, 12913,  1859, 56987, 43246, 28982,
     49802,  6994, 27943, 46335, 33229, 22549, 11872, 63416,
     21765, 36061, 64168,  9072,  5698, 53146, 47599, 24631,
     54155,  2643, 31782, 42494, 37068, 18708, 16225, 59065,
     26118, 49118, 51627,  4211,  9537, 64665, 35564, 21300,
     57480, 14672, 20261, 38653, 41935, 31255,  3170, 54714,
     30471, 44767, 55466,   370, 13376, 60824, 39917, 16949,
     61833, 10321, 24100, 34812, 45774, 27414,  7523, 50363,
     34824, 20944, 10149, 65149, 52047,  4759, 25826, 48442,
      3718, 55134, 41259, 30963, 19905, 37913, 57964, 15284,
     39177, 16593, 13988, 61308, 55886,   918, 30179, 44091,
      8071, 50783, 45098, 27122, 23744, 34072, 62317, 10933,
     43530, 29650,  1447, 56447, 59725, 12437, 18144, 40760,
     11396, 62812, 33577, 23281, 28611, 46619, 49262,  6582,
     47883, 25299,  5286, 52606, 63564,  8596, 22497, 36409,
     15749, 58461, 37416, 19440, 32450, 42778, 53615,  2231,
     52236,  5588, 25505, 47737, 36683, 22163,  8422, 63806,
     19074, 37722, 58671, 15607,  2501, 53277, 42600, 32688,
     56589,  1237, 29344, 43896, 40522, 18322, 12775, 59455,
     23427, 33371, 62510, 11766,  6340, 49436, 46953, 28337,
     60942, 14294, 16803, 39035, 44361, 29841,   740, 56124,
     26752, 45400, 50989,  7925, 11207, 61983, 33898, 23986,
     65295,  9943, 20642, 35194, 48200, 26000,  5093, 51773,
     31105, 41049, 54828,  4084, 15046, 58142, 38251, 19635],
    [    0, 27757, 55514, 46263, 44457, 49604, 30067,  6430,
     18255, 11042, 40853, 62456, 60134, 34443, 12860, 24145,
     36510, 58099, 22084, 14889,  9015, 20314, 64493, 38784,
     51665, 42428,  4363, 32102, 25720,  2069, 48290, 53455,
       289, 27980, 55803, 46486, 44168, 49381, 29778,  6207,
     18030, 10755, 40628, 62169, 60359, 34730, 13085, 24432,
     36799, 58322, 22373, 15112,  8726, 20091, 64204, 38561,
     51440, 42141,  4138, 31815, 25945,  2356, 48515, 53742,
       578, 28207, 55960, 46837, 45035, 50054, 30513,  7004,
     17677, 10592, 40407, 61882, 59556, 33993, 12414, 23571,
     36060, 57521, 21510, 14443,  8565, 19736, 63919, 38338,
     52115, 43006,  4937, 32548, 26170,  2647, 48864, 53901,
       867, 28430, 56249, 47060, 44746, 49831, 30224,  6781,
     17452, 10305, 40182, 61595, 59781, 34280, 12639, 23858,
     36349, 57744, 21799, 14666,  8276, 19513, 63630, 38115,
     51890, 42719,  4712, 32261, 26395,  2934, 49089, 54188,
      1156, 26857, 56414, 45107, 43309, 50496, 29175,  7578,
     17355, 12198, 39697, 63356, 61026, 33295, 14008, 23253,
     35354, 58999, 21184, 16045, 10163, 19422, 65385, 37636,
     52565, 41272,  5519, 31202, 24828,  3217, 47142, 54347,
      1445, 27080, 56703, 45330, 43020, 50273, 28886,  7355,
     17130, 11911, 39472, 63069, 61251, 33582, 14233, 23540,
     35643, 59222, 21473, 16268,  9874, 19199, 65096, 37413,
     52340, 40985,  5294, 30915, 25053,  3504, 47367, 54634,
      1734, 27307, 56860, 45681, 43887, 50946, 29621,  8152,
     16777, 11748, 39251, 62782, 60448, 32845, 13562, 22679,
     34904, 58421, 20610, 15599,  9713, 18844, 64811, 37190,
     53015, 41850,  6093, 31648, 25278,  3795, 47716, 54793,
      2023, 27530, 57149, 45904, 43598, 50723, 29332,  7929,
     16552, 11461, 39026, 62495, 60673, 33132, 13787, 22966,
     35193, 58644, 20899, 15822,  9424, 18621, 64522, 36967,
     52790, 41563,  5868, 31361, 25503,  4082, 47941, 55080],
    [    0, 47289, 28015, 54742, 56030, 25191, 47025,  3848,
     43425,  4376, 50382, 31863, 29567, 52166,  7696, 42665,
     20319, 63462,  8752, 39561, 38273, 11576, 63726, 16471,
     59134, 24135, 35729, 13096, 15392, 33945, 20815, 59894,
     40638,  9735, 62417, 19304, 17504, 64729, 10511, 37302,
     14111, 36774, 23152, 58057, 60865, 21880, 32942, 14359,
     53729, 26968, 48270,  1079,  2879, 45958, 26192, 57065,
     30784, 49401,  5423, 44438, 41630,  6695, 53233, 30536,
      8545, 39384, 19470, 62647, 64447, 17158, 38608, 11881,
     35008, 12409, 58799, 23830, 21022, 60071, 16241, 34760,
     28222, 54919,   849, 48104, 46304,  3161, 55695, 24886,
     51103, 32550, 43760,  4681,  7489, 42488, 28718, 51351,
     49119,  1894, 53936, 27145, 25857, 56760,  2158, 45271,
      5758, 44743, 31505, 50088, 52384, 29721, 41423,  6518,
     61568, 18489, 40431,  9558, 10846, 37607, 18225, 65416,
     22817, 57752, 13390, 36087, 33791, 15174, 61072, 22057,
     17090, 64123, 12205, 38676, 38940,  8357, 62835, 19914,
     60259, 21466, 34316, 16053, 12733, 35076, 23762, 58475,
      3485, 46372, 24818, 55371, 55107, 28666, 47660,   661,
     42044,  7301, 51539, 29162, 32482, 50779,  5005, 43828,
     56444, 25797, 45331,  2474,  1698, 48667, 27597, 54132,
     30173, 52580,  6322, 40971, 44803,  6074, 49772, 31445,
     37667, 11162, 65100, 18165, 18941, 61764,  9362, 39979,
     14978, 33339, 22509, 61268, 57436, 22757, 36147, 13706,
     25507, 56090,  3788, 46709, 47485,   452, 54290, 27819,
     51714, 29371, 42861,  8148,  4316, 43109, 32179, 50442,
     11516, 37957, 16787, 63786, 63010, 20123, 39757,  9204,
     34141, 15844, 59442, 20619, 24451, 59194, 13036, 35413,
     64797, 17828, 36978, 10443, 10179, 40826, 19116, 61973,
     21692, 60421, 14803, 33130, 36450, 14043, 58125, 23476,
     45634,  2811, 57133, 26516, 26780, 53285,  1523, 48458,
      7139, 41818, 30348, 52789, 49469, 31108, 44114,  5355],
    [    0, 53971, 47547, 27496, 28523, 48568, 54992,  1027,
     57046,  3077, 26477, 46526, 45501, 25454,  2054, 56021,
     41393, 29538,  6154, 51929, 52954,  7177, 30561, 42418,
     32615, 44468, 50908,  5135,  4108, 49887, 43447, 31588,
     24447, 36268, 59076, 13335, 12308, 58055, 35247, 23420,
     33193, 21370, 14354, 60097, 61122, 15377, 22393, 34218,
     65230, 11293, 18293, 38310, 37285, 17270, 10270, 64205,
      8216, 62155, 39331, 19312, 20339, 40352, 63176,  9243,
     48894, 27693,  1861, 54678, 53653,   838, 26670, 47869,
     24616, 45819, 55699,  2880,  3907, 56720, 46840, 25643,
      8015, 52636, 42740, 29735, 28708, 41719, 51615,  6988,
     49561,  4938, 30754, 43761, 44786, 31777,  5961, 50586,
     57729, 13138, 22586, 35561, 36586, 23609, 14161, 58754,
     16215, 60804, 34540, 21567, 20540, 33519, 59783, 15188,
     16432, 37603, 63883, 11096, 12123, 64904, 38624, 17459,
     40678, 19509, 10077, 62862, 61837,  9054, 18486, 39653,
     25057, 45874, 55386,  2697,  3722, 56409, 46897, 26082,
     48951, 28132,  1676, 54367, 53340,   655, 27111, 47924,
     49232,  4739, 31211, 43832, 44859, 32232,  5760, 50259,
      7814, 52309, 42813, 30190, 29165, 41790, 51286,  6789,
     16030, 60493, 34597, 22006, 20981, 33574, 59470, 15005,
     57416, 12955, 23027, 35616, 36643, 24048, 13976, 58443,
     40751, 19964,  9876, 62535, 61508,  8855, 18943, 39724,
     16889, 37674, 63554, 10897, 11922, 64577, 38697, 17914,
     57119,  3532, 26276, 46199, 45172, 25255,  2511, 56092,
       457, 54042, 47218, 27297, 28322, 48241, 55065,  1482,
     32430, 44157, 50965,  5574,  4549, 49942, 43134, 31405,
     41080, 29355,  6595, 51984, 53011,  7616, 30376, 42107,
     32864, 21171, 14811, 60168, 61195, 15832, 22192, 33891,
     24246, 35941, 59149, 13790, 12765, 58126, 34918, 23221,
      8657, 62210, 39018, 19129, 20154, 40041, 63233,  9682,
     65287, 11732, 18108, 37999, 36972, 17087, 10711, 64260],
    [    0, 59366, 54225, 13367, 48063, 23641, 26734, 36744,
     27491, 35973, 47282, 24404, 53468, 14138,   781, 58603,
     54982, 12576,  1303, 58097, 28025, 35487, 48808, 22862,
     48549, 23107, 28276, 35218,  1562, 57852, 54731, 12845,
     45457, 22135, 25152, 34214,  2606, 60872, 55807, 15897,
     56050, 15636,  2339, 61125, 24909, 34475, 45724, 21882,
     26455, 32945, 46214, 21344, 56552, 15118,  3897, 59615,
      3124, 60370, 57317, 14339, 46987, 20589, 25690, 33724,
     32575, 39129, 44270, 19208, 50304,  9062,  5969, 61623,
      5212, 62394, 51085,  8299, 45027, 18437, 31794, 39892,
     43513, 19999, 31272, 40398,  4678, 62880, 49559,  9841,
     49818,  9596,  4427, 63149, 31013, 40643, 43764, 19730,
     52910, 10568,  7551, 64153, 29969, 37623, 42688, 16678,
     42445, 16939, 30236, 37370,  7794, 63892, 52643, 10821,
      6248, 65422, 52153, 11359, 41943, 17457, 28678, 38880,
     29451, 38125, 41178, 18236, 51380, 12114,  7013, 64643,
     65150,  6552, 11695, 51785, 17857, 41511, 38416, 29174,
     38173, 29435, 18124, 41258, 11938, 51524, 64883,  6805,
     10424, 53086, 64361,  7311, 37639, 29921, 16598, 42800,
     17371, 42045, 36874, 30700, 63588,  8066, 11189, 52307,
     20463, 43017, 39998, 31704, 62544,  5046, 10113, 49255,
      9356, 50026, 63325,  4283, 40755, 30933, 19682, 43780,
     39209, 32463, 19192, 44318,  8854, 50544, 61767,  5793,
     62026,  5548,  8603, 50813, 18933, 44563, 39460, 32194,
     33089, 26279, 21136, 46454, 15102, 56600, 59695,  3785,
     59938,  3524, 14835, 56853, 20893, 46715, 33356, 26026,
     22407, 45153, 33878, 25520, 60472,  3038, 16361, 55311,
     15588, 56066, 61237,  2259, 34651, 24765, 21642, 45932,
     12496, 55094, 58113,  1255, 35695, 27785, 22718, 48984,
     23475, 48213, 34914, 28548, 57356,  2026, 13277, 54331,
     58902,   496, 13767, 53793, 23977, 47695, 36472, 27038,
     36213, 27283, 24228, 47426, 14026, 53548, 58651,   765],
    [    0, 29554, 59108, 38294, 53717, 41639, 14129, 17475,
     49079, 52421, 22867, 10785, 28258,  7440, 34950, 64500,
     25459,  4097, 34199, 63205, 45734, 49620, 21570, 10032,
     56516, 44982, 14880, 18770,  3345, 32355, 60405, 39047,
     50918, 46484,  8194, 21360,  5939, 25665, 61911, 33445,
     31057,  2595, 40885, 60615, 43140, 56310, 20064, 15634,
     42389, 55015, 17265, 12291, 29760,  1842, 37540, 57814,
      6690, 26960, 64710, 36788, 52215, 47237, 11539, 24161,
     37329, 58019, 30517,  1095, 16388, 13174, 42720, 54674,
     11878, 23828, 51330, 48112, 65459, 36033,  6487, 27173,
     62114, 33232,  5190, 26420,  9079, 20485, 50579, 46817,
     19733, 15975, 44017, 55427, 40128, 61362, 31268,  2390,
     22327,  9285, 45523, 49825, 34530, 62864, 24582,  4980,
     59520, 39922,  3684, 32022, 14677, 18983, 57265, 44227,
     13380, 18230, 53920, 41426, 58769, 38627,   885, 28679,
     35827, 63617, 27927,  7781, 23078, 10580, 48322, 53168,
     16319, 19661, 55643, 43561, 61034, 40216,  2190, 31740,
     32776, 62330, 26348,  5534, 20957,  8879, 46905, 50251,
     23756, 12222, 47656, 51546, 36121, 65131, 27645,  6287,
     58235, 36873,  1439, 30445, 12974, 16860, 54346, 42808,
     63833, 35371,  8125, 27855, 10380, 23550, 52840, 48410,
     18158, 13724, 40970, 54136, 38715, 58441, 29151,   685,
     39466, 59736, 31950,  4028, 19455, 14477, 44315, 56937,
      9629, 22255, 50041, 45067, 62536, 34618,  4780, 25054,
     44654, 56604, 18570, 15352, 32699,  3273, 39263, 59949,
      4569, 25259, 63293, 33871, 49164, 45950,  9960, 21914,
     52509, 48751, 11257, 22667,  7368, 28602, 64044, 35166,
     29354,   472, 37966, 59196, 41855, 53261, 17819, 14057,
     26760,  7162, 36460, 64798, 47453, 51759, 24505, 11467,
     55103, 42061, 12763, 17065,  1770, 30104, 57358, 37756,
      3067, 30857, 60703, 40557, 55854, 43356, 15562, 20408,
     46156, 51006, 21160,  8666, 26009,  5867, 33661, 61455],
    [    0, 14648, 29296, 19272, 58592, 56792, 38544, 44968,
     54749, 60645, 42925, 40597, 12605,  2053, 17229, 31349,
     47015, 36511, 50647, 64751, 21319, 27263,  8503,  6159,
     25210, 23362,  4106, 10546, 34458, 49058, 62698, 52690,
     29523, 19051,   291, 14363, 38835, 44683, 58819, 56571,
     42638, 40886, 54526, 60870, 17006, 31574, 12318,  2342,
     50420, 64972, 46724, 36796,  8212,  6444, 21092, 27484,
      4393, 10257, 25433, 23137, 62921, 52465, 34745, 48769,
     59046, 57246, 38102, 44526,   582, 15230, 28726, 18702,
     13179,  2627, 16651, 30771, 55195, 61091, 42475, 40147,
     20737, 26681,  9073,  6729, 46561, 36057, 51089, 65193,
     34012, 48612, 63148, 53140, 24636, 22788,  4684, 11124,
     38389, 44237, 59269, 57021, 28949, 18477,   869, 14941,
     16424, 30992, 12888,  2912, 42184, 40432, 54968, 61312,
      8786,  7018, 20514, 26906, 50866, 65418, 46274, 36346,
     63375, 52919, 34303, 48327,  4975, 10839, 24863, 22567,
     53585, 59497, 41761, 39449, 13745,  3209, 18369, 32505,
      1164, 15796, 30460, 20420, 57452, 55636, 37404, 43812,
     26358, 24526,  5254, 11710, 33302, 47918, 61542, 51550,
     45867, 35347, 49499, 63587, 22475, 28403,  9659,  7299,
     41474, 39738, 53362, 59722, 18146, 32730, 13458,  3498,
     30687, 20199,  1455, 15511, 37695, 43527, 57679, 55415,
      5541, 11421, 26581, 24301, 61765, 51325, 33589, 47629,
     49272, 63808, 45576, 35632,  9368,  7584, 22248, 28624,
     14327,  3791, 17799, 31935, 54039, 59951, 41319, 39007,
     57898, 56082, 36954, 43362,  1738, 16370, 29882, 19842,
     32848, 47464, 61984, 51992, 25776, 23944,  5824, 12280,
     21901, 27829, 10237,  7877, 45421, 34901, 49949, 64037,
     17572, 32156, 14036,  4076, 41028, 39292, 53812, 60172,
     37241, 43073, 58121, 55857, 30105, 19617,  2025, 16081,
     62211, 51771, 33139, 47179,  6115, 11995, 26003, 23723,
      9950,  8166, 21678, 28054, 49726, 64262, 45134, 35190],
    [    0,  7197, 14394,  9255, 28788, 27753, 18510, 21587,
     57576, 64757, 55506, 50383, 37020, 35969, 43174, 46267,
     56781, 49616, 58871, 63978, 44473, 45476, 38275, 35230,
     15653,  8504,  1311,  6402, 19793, 20812, 30059, 26998,
     42887, 48026, 40893, 33696, 55283, 52206, 61385, 62420,
     18287, 23410, 32597, 25416, 14107, 11014,  3873,  4924,
     31306, 26199, 17008, 24173,  2622,  5667, 12804, 11801,
     39586, 34495, 41624, 48773, 60118, 63179, 53996, 52977,
     21267, 20238, 27433, 30516,  9063, 16250,  7005,  1856,
     46075, 45030, 35777, 38876, 50063, 57234, 64437, 59304,
     36574, 37571, 46820, 43769, 65194, 58039, 50832, 55949,
     28214, 29227, 22028, 18961,  7746,   607,  9848, 14949,
     62612, 59529, 52398, 53427, 34016, 39165, 48346, 41159,
      5244,  2145, 11334, 12379, 25608, 30741, 23602, 16431,
     10585, 13636,  4451,  3454, 22829, 17712, 24855, 32010,
     51633, 54700, 61835, 60822, 47557, 42456, 33279, 40418,
     42534, 47675, 40476, 33281, 54866, 51791, 61032, 62069,
     18126, 23251, 32500, 25321, 14010, 10919,  3712,  4765,
     31723, 26614, 17361, 24524,  2975,  6018, 13221, 12216,
     39683, 34590, 41785, 48932, 60279, 63338, 54093, 53072,
       417,  7612, 14747,  9606, 29141, 28104, 18927, 22002,
     57673, 64852, 55667, 50542, 37181, 36128, 43271, 46362,
     56428, 49265, 58454, 63563, 44056, 45061, 37922, 34879,
     15492,  8345,  1214,  6307, 19696, 20717, 29898, 26839,
     62773, 59688, 52495, 53522, 34113, 39260, 48507, 41318,
      5597,  2496, 11751, 12794, 26025, 31156, 23955, 16782,
     10488, 13541,  4290,  3295, 22668, 17553, 24758, 31915,
     51216, 54285, 61482, 60471, 47204, 42105, 32862, 40003,
     21170, 20143, 27272, 30357,  8902, 16091,  6908,  1761,
     45658, 44615, 35424, 38525, 49710, 56883, 64020, 58889,
     36735, 37730, 46917, 43864, 65291, 58134, 50993, 56108,
     28567, 29578, 22445, 19376,  8163,  1022, 10201, 15300],
    [    0, 32897,  7455, 40350, 14910, 47807, 10017, 42912,
     29820, 62717, 26979, 59874, 20034, 52931, 21341, 54236,
     59640, 26745, 62951, 30054, 53958, 21063, 53209, 20312,
     40068,  7173, 33179,   282, 42682,  9787, 48037, 15140,
     52717, 19820, 53490, 20595, 63443, 30546, 60108, 27213,
     47505, 14608, 42126,  9231, 33711,   814, 40624,  7729,
      9493, 42388, 14346, 47243,  7979, 40874,   564, 33461,
     20841, 53736, 19574, 52471, 27479, 60374, 30280, 63177,
     34759,  1862, 39640,  6745, 48633, 15736, 41190,  8295,
     62395, 29498, 61092, 28197, 51589, 18692, 54426, 21531,
     28479, 61374, 29216, 62113, 21761, 54656, 18462, 51359,
      6979, 39874,  1628, 34525,  8573, 41468, 15458, 48355,
     18986, 51883, 22325, 55220, 28692, 61589, 27915, 60810,
     15958, 48855,  9033, 41928,  1128, 34025,  6519, 39414,
     41682,  8787, 49101, 16204, 39148,  6253, 34291,  1394,
     54958, 22063, 52145, 19248, 60560, 27665, 61839, 28942,
      5011, 37650,  3724, 36365, 10669, 43308, 13490, 46131,
     26607, 59246, 31472, 64113, 24017, 56656, 16590, 49231,
     64363, 31722, 58996, 26357, 49493, 16852, 56394, 23755,
     36631,  3990, 37384,  4745, 46377, 13736, 43062, 10423,
     56958, 24319, 50017, 17376, 58432, 25793, 63839, 31198,
     43522, 10883, 46877, 14236, 36924,  4285, 36131,  3490,
     13958, 46599, 11161, 43800,  3256, 35897,  4519, 37158,
     17146, 49787, 24549, 57188, 30916, 63557, 26075, 58714,
     37972,  5333, 35147,  2506, 44650, 12011, 45941, 13300,
     57384, 24745, 64823, 32182, 55830, 23191, 50953, 18312,
     31916, 64557, 25011, 57650, 18066, 50707, 23437, 56076,
      2256, 34897,  5583, 38222, 13038, 45679, 12273, 44912,
     22969, 55608, 17574, 50215, 25479, 58118, 32408, 65049,
     11717, 44356, 12506, 45147,  6139, 38778,  2788, 35429,
     45377, 12736, 44126, 11487, 35711,  3070, 38496,  5857,
     50493, 17852, 55330, 22691, 65283, 32642, 57884, 25245],
    [    0, 52943, 33155, 20300,  7963, 53716, 40600, 20567,
     15926, 61689, 49077, 29050,  8493, 61410, 41134, 28257,
     31852, 45731, 65007, 13088, 25463, 44472, 58100, 11323,
     16986, 35989, 50137,  3350, 23873, 37774, 56514,  4621,
     63704, 13847, 31067, 46996, 59331, 10508, 26176, 43151,
     50926,  2081, 18285, 35234, 55797,  5946, 22646, 38585,
     33972, 19067,  1335, 52216, 39855, 21856,  6700, 54499,
     47746, 29773, 15105, 62926, 42393, 27478,  9242, 60117,
     60845,  9058, 27694, 41697, 62134, 15481, 29493, 48634,
     54171,  7508, 21016, 40151, 52352,   591, 19715, 33740,
     37313, 24334,  4162, 56973, 36570, 16405,  3929, 49558,
     45047, 24888, 11892, 57531, 45292, 32291, 12655, 65440,
      5493, 56250, 38134, 23097,  2670, 50337, 35821, 17698,
     11075, 58764, 43712, 25615, 13400, 64151, 46555, 31508,
     26905, 42966, 59546,  9813, 30210, 47309, 63361, 14670,
     22319, 39392, 54956,  6243, 18484, 34555, 51639,  1912,
     51015,  2440, 18116, 34827, 55388,  5779, 23007, 38672,
     63857, 14270, 30962, 46653, 58986, 10405, 26601, 43302,
     47915, 30180, 15016, 62567, 42032, 27391,  9651, 60284,
     34077, 19410,  1182, 51793, 39430, 21705,  7045, 54602,
     16287, 61776, 48668, 28883,  8324, 61003, 41223, 28616,
       425, 53094, 32810, 20197,  7858, 53373, 40753, 20990,
     17395, 36156, 49776,  3263, 23784, 37415, 56683,  5028,
     32197, 45834, 64582, 12937, 25310, 44049, 58205, 11666,
     10986, 58405, 43881, 26022, 13809, 64318, 46194, 31421,
      5340, 55827, 38239, 23440,  3015, 50440, 35396, 17547,
     22150, 38985, 55045,  6602, 18845, 34642, 51230,  1745,
     26800, 42623, 59699, 10236, 30635, 47460, 63016, 14567,
     53810,  7421, 21425, 40318, 52521,   998, 19626, 33381,
     60420,  8907, 28039, 41800, 62239, 15824, 29340, 48211,
     44638, 24721, 12253, 57618, 45381, 32650, 12486, 65033,
     36968, 24231,  4587, 57124, 36723, 16828,  3824, 49215],
    [    0, 59880, 53197,  9765, 33671, 27247, 19530, 42402,
      6931, 62203, 54494, 15670, 39060, 29052, 22361, 48817,
     13862, 57294, 63979,  4099, 46497, 23625, 31340, 37764,
     11573, 50397, 58104,  2832, 44722, 18266, 24959, 34967,
     27724, 34212, 41857, 19049, 61387,  1571,  8198, 51694,
     30559, 40631, 47250, 20858, 62680,  7472, 15125, 54013,
     23146, 45954, 38311, 31823, 55789, 12293,  5664, 65480,
     16761, 43153, 36532, 26460, 49918, 11030,  3379, 58587,
     55448, 12656,  5973, 65213, 23327, 45815, 38098, 32058,
     50059, 10851,  3142, 58798, 16396, 43492, 36801, 26153,
     61118,  1878,  8563, 51355, 27961, 34001, 41716, 19228,
     62893,  7237, 14944, 54152, 30250, 40898, 47591, 20495,
     46292, 23868, 31513, 37617, 14163, 57019, 63646,  4470,
     44999, 17967, 24586, 35298, 11328, 50600, 58253,  2661,
     33522, 27418, 19775, 42199,   373, 59549, 52920, 10064,
     39393, 28681, 22060, 49092,  6758, 62350, 54699, 15427,
     44333, 17605, 25312, 35592, 11946, 51010, 57703,  2191,
     46654, 24534, 31219, 36891, 13753, 56401, 64116,  5020,
     39691, 29411, 21702, 48430,  6284, 61796, 55105, 16041,
     32792, 27120, 20437, 42557,   927, 60023, 52306,  9658,
     49505, 10377,  3756, 59204, 17126, 43790, 36139, 25795,
     55922, 13210,  5567, 64599, 23029, 45085, 38456, 32720,
     63303,  7855, 14474, 53602, 29888, 40232, 47885, 21221,
     60500,  1468,  9113, 51825, 28627, 34363, 40990, 18934,
     30133, 40029, 47736, 21392, 63026,  8154, 14847, 53271,
     28326, 34638, 41323, 18563, 60705,  1225,  8940, 51972,
     17299, 43643, 35934, 26038, 49172, 10748,  4057, 58929,
     22656, 45416, 38733, 32421, 56071, 13039,  5322, 64802,
      6649, 61457, 54836, 16348, 39550, 29590, 21939, 48219,
       746, 60162, 52519,  9423, 33133, 26757, 20128, 42824,
     12255, 50743, 57362,  2554, 44120, 17840, 25493, 35453,
     13516, 56612, 64257,  4841, 46923, 24227, 30854, 37230],
    [    0, 29813, 59626, 40095, 52681, 47548,  9507, 20822,
     34703, 62458, 28517,  6928, 19014, 15923, 41644, 55001,
      4867, 26486, 64489, 36764, 57034, 43711, 13856, 16981,
     38028, 57593, 31846,  2067, 22853, 11568, 45487, 50650,
      9734, 21107, 52972, 47769, 60367, 40890,   805, 30544,
     41353, 54780, 18787, 15638, 27712,  6197, 33962, 61663,
     13573, 16752, 56815, 43418, 63692, 36025,  4134, 25683,
     45706, 50943, 23136, 11797, 32579,  2870, 38825, 58332,
     19468, 14457, 42214, 53395, 33221, 62896, 26927,  7514,
     52099, 49142,  9065, 22300,  1610, 29247, 61088, 39637,
     24335, 11130, 47077, 50064, 37574, 59059, 31276,  3673,
     55424, 44277, 12394, 17439,  5449, 24892, 64931, 35286,
     27146,  7807, 33504, 63125, 42947, 54198, 20265, 15196,
     60805, 39408,  1391, 28954,  8268, 21561, 51366, 48339,
     30985,  3452, 37347, 58774, 46272, 49333, 23594, 10335,
     65158, 35571,  5740, 25113, 13135, 18234, 56229, 45008,
     38936, 60525, 28914,  1159, 21969,  8612, 48443, 51534,
      8087, 27618, 63357, 33544, 53854, 42539, 15028, 20161,
     35611, 65390, 25585,  6020, 18130, 12967, 44600, 55885,
      3220, 30945, 58494, 36875, 49501, 46376, 10679, 24002,
     48670, 51819, 22260,  8833, 29655,  1954, 39741, 61256,
     14737, 19940, 53627, 42254, 62552, 32813,  7346, 26823,
     44317, 55656, 17911, 12674, 24788,  5281, 34878, 64587,
     10898, 24295, 49784, 46605, 59227, 37678,  4017, 31684,
     54292, 41057, 15614, 18571,  6621, 28072, 61751, 34114,
     21403, 10222, 47985, 52996, 40530, 59943, 30392,   717,
     50967, 45922, 12285, 23432,  2782, 32427, 57908, 38465,
     16536, 13549, 43122, 56327, 36177, 63780, 26043,  4558,
     61970, 34407,  6904, 28301, 16347, 19374, 55089, 41796,
     30109,   488, 40311, 59650, 47188, 52257, 20670,  9419,
     57617, 38244,  2555, 32142, 11480, 22701, 50226, 45127,
     26270,  4843, 36468, 64001, 43863, 57122, 17341, 14280],
    [    0, 46261, 30071, 49602, 60142, 24155, 40857, 11052,
     51649, 32116, 48310,  2051,  9007, 38810, 22104, 58093,
     36767, 15146, 64232, 20061, 25969, 53700,  4102, 42163,
     18014, 62187, 13097, 34716, 44208,  6149, 55751, 28018,
       803, 46998, 30292, 49889, 59853, 23928, 40122, 10255,
     51938, 32343, 49045,  2848,  8204, 38073, 21883, 57806,
     36028, 14345, 63947, 19838, 26194, 53991,  4901, 42896,
     17789, 61896, 12298, 33983, 44947,  6950, 56036, 28241,
      1606, 45811, 29489, 51076, 60584, 22557, 39391, 11626,
     53127, 31538, 47856,  3653,  9577, 37340, 20510, 58539,
     35289, 15724, 64686, 18459, 25399, 55170,  5696, 41717,
     16408, 62637, 13679, 33242, 43766,  7747, 57217, 27444,
      1381, 45520, 28690, 50343, 61323, 23358, 39676, 11849,
     52388, 30737, 47571,  3430,  9802, 37631, 21309, 59272,
     35578, 15951, 65421, 19256, 24596, 54433,  5475, 41430,
     17211, 63374, 13900, 33529, 43477,  7520, 56482, 26647,
      3212, 47161, 31227, 52558, 58978, 21207, 37653, 10144,
     50509, 29176, 45114,  1167, 12195, 39702, 23252, 61025,
     33555, 14246, 63076, 17105, 27133, 56648,  7306, 43071,
     19154, 65127, 16293, 35600, 41020,  5257, 54603, 25086,
      4015, 47898, 31448, 52845, 58689, 20980, 36918,  9347,
     50798, 29403, 45849,  1964, 11392, 38965, 23031, 60738,
     32816, 13445, 62791, 16882, 27358, 56939,  8105, 43804,
     18929, 64836, 15494, 34867, 41759,  6058, 54888, 25309,
      2762, 48767, 32701, 51976, 57380, 21649, 38227,  8678,
     49931, 30654, 46716,   713, 10725, 40272, 23698, 59431,
     34133, 12768, 61474, 17559, 28603, 56078,  6860, 44665,
     19604, 63521, 14819, 36182, 42618,  4815, 54029, 26552,
      2537, 48476, 31902, 51243, 58119, 22450, 38512,  8901,
     49192, 29853, 46431,   490, 10950, 40563, 24497, 60164,
     34422, 12995, 62209, 18356, 27800, 55341,  6639, 44378,
     20407, 64258, 15040, 36469, 42329,  4588, 53294, 25755],
    [    0, 54485, 46519, 24930, 30579, 41894, 49860,  5649,
     61158, 14899, 23377, 36740, 39317, 19776, 11298, 63735,
     49617,  5380, 29798, 41139, 46754, 25207,   789, 55232,
     12087, 64482, 39552, 20053, 22596, 35985, 60915, 14630,
     40895, 19306, 10760, 65245, 59596, 15385, 23931, 35246,
     29017, 42380, 50414,  4155,  1578, 54015, 45981, 26440,
     24174, 35515, 60377, 16140, 10525, 64968, 40106, 18559,
     45192, 25693,  1343, 53738, 51195,  4910, 29260, 42649,
      9059, 63414, 38612, 16897, 21520, 32965, 57767, 13682,
     52613,  6480, 30770, 44263, 47862, 28195,  3905, 56212,
     58034, 13927, 22277, 33744, 38337, 16660,  8310, 62627,
      3156, 55425, 47587, 27958, 31527, 45042, 52880,  6725,
     48348, 26633,  2411, 56766, 52143,  8058, 32280, 43725,
     21050, 34543, 59277, 13144,  9545, 61852, 37118, 17451,
     32013, 43480, 51386,  7279,  2686, 57003, 49097, 27420,
     37867, 18238,  9820, 62089, 58520, 12365, 20783, 34298,
     18118, 37395, 62321, 10148, 12725, 58720, 33794, 20695,
     43040, 31989,  7575, 51522, 57171,  2950, 27364, 48689,
     34583, 21442, 12960, 58997, 61540,  9393, 17875, 37126,
     27121, 48420, 56390,  2195,  7810, 51799, 43829, 32736,
     55673,  3500, 27854, 47131, 44554, 31455,  7101, 53096,
     14239, 58186, 33320, 22269, 16620, 37945, 62811,  8590,
      6312, 52349, 44319, 31178, 28635, 47886, 55916,  3769,
     63054,  8859, 17401, 38700, 33085, 21992, 13450, 57439,
     26021, 45424, 53266,  1223,  4822, 50691, 42849, 29620,
     35651, 24470, 16116, 59937, 64560, 10469, 18823, 40274,
     42100, 28833,  4547, 50454, 54023,  2002, 26288, 45669,
     19090, 40519, 65317, 11248, 15841, 59700, 34902, 23683,
     64026, 11983, 20397, 39800, 36201, 22972, 14558, 60427,
      5372, 49193, 41291, 30110, 25487, 46938, 54840,   749,
     15307, 61214, 36476, 23209, 19640, 39021, 63759, 11738,
     54573,   504, 24730, 46159, 41566, 30347,  6121, 49980],
    [    0, 58597, 54743, 12594, 47027, 21334, 25188, 34433,
     29563, 38814, 42668, 16969, 50376,  8237,  4383, 62970,
     59126,   531, 13089, 55236, 20805, 46496, 33938, 24695,
     38285, 29032, 16474, 42175,  8766, 50907, 63465,  4876,
     53745, 13588,  1062, 57539, 26178, 33447, 45973, 22384,
     41610, 18031, 30557, 37816,  5433, 61916, 49390,  9227,
     14087, 54242, 58064,  1589, 32948, 25681, 21859, 45446,
     17532, 41113, 37291, 30030, 62415,  5930,  9752, 49917,
     49151, 23322, 27176, 36557,  2124, 60585, 56731, 14718,
     52356, 10337,  6483, 64950, 31543, 40914, 44768, 18949,
     22793, 48620, 36062, 26683, 61114,  2655, 15213, 57224,
     10866, 52887, 65445,  6976, 40385, 31012, 18454, 44275,
     28174, 35563, 48089, 24380, 55741, 15704,  3178, 59535,
      7541, 63888, 51362, 11335, 43718, 20003, 32529, 39924,
     35064, 27677, 23855, 47562, 16203, 56238, 60060,  3705,
     64387,  8038, 11860, 51889, 19504, 43221, 39399, 32002,
     25571, 34566, 46644, 21201, 54352, 12469,   391, 58722,
      4248, 62589, 50511,  8618, 42795, 17358, 29436, 38425,
     34069, 25072, 20674, 46119, 12966, 54851, 59249,   916,
     63086,  4747,  9145, 51036, 16861, 42296, 37898, 28911,
     45586, 22263, 26565, 33568,  1441, 57668, 53366, 13459,
     49513,  9612,  5310, 61531, 30426, 37439, 41741, 18408,
     21732, 45057, 33075, 26070, 58199,  1970, 13952, 53861,
     10143, 50042, 62024,  5805, 36908, 29897, 17915, 41246,
     56348, 14585,  2507, 60718, 27567, 36682, 48760, 23197,
     44903, 19330, 31408, 40533,  6356, 64561, 52483, 10726,
     15082, 56847, 61245,  3032, 36185, 27068, 22670, 48235,
     18833, 44404, 40006, 30883, 65058,  6855, 11253, 53008,
      3565, 59656, 55354, 15583, 47710, 24251, 28553, 35692,
     32406, 39539, 43841, 20388, 51493, 11712,  7410, 63511,
     60187,  4094, 16076, 55849, 23720, 47181, 35199, 28058,
     39008, 31877, 19895, 43346, 12243, 52022, 64004,  7905],
    [    0, 64765, 58855,  6426, 55251, 11054, 12852, 52937,
     46011, 20294, 22108, 43681, 25704, 39061, 33167, 32114,
     31595, 34710, 40588, 25201, 44216, 20549, 18783, 46498,
     51408, 13357, 11575, 53706,  7939, 58366, 64228,  1561,
     63190,  2603,  4913, 61388,  8453, 56824, 50402, 14367,
     17773, 47504, 41098, 23671, 37566, 28227, 30553, 35748,
     36285, 28992, 26714, 38055, 23150, 42643, 49033, 17268,
     15878, 49915, 56289, 10012, 59861,  5416,  3122, 61647,
     61873,  3404,  5206, 59563,  9826, 55967, 50053, 16248,
     16906, 48887, 42989, 23312, 38361, 26916, 28734, 36035,
     35546, 30247, 28477, 37824, 23817, 41460, 47342, 17427,
     14689, 50588, 56454,  8315, 61106,  4687,  2901, 63400,
      1895, 64410, 57984,  7805, 53428, 11337, 13651, 51630,
     46300, 18465, 20795, 44486, 25359, 40946, 34536, 31253,
     31756, 33009, 39403, 25878, 43999, 22306, 20024, 45765,
     53175, 13130, 10832, 54957,  6244, 58521, 64899,   382,
     65407,   898,  6808, 58981, 10412, 54353, 52555, 12726,
     19652, 45113, 43299, 21982, 39703, 26602, 32496, 33293,
     33812, 30953, 25075, 40206, 21447, 44858, 46624, 19165,
     14255, 52050, 53832, 11957, 57468,  7297,  1435, 63846,
      2473, 62804, 60494,  4275, 56954,  8839, 15261, 51040,
     47634, 18159, 24565, 41736, 28097, 37180, 34854, 29915,
     29378, 36415, 38693, 27608, 42257, 23020, 16630, 48139,
     49529, 15748,  9374, 55395,  5802, 59991, 62285,  4016,
      3790, 62003, 60201,  6100, 55581,  9696, 15610, 49159,
     48501, 16776, 22674, 42095, 27302, 38491, 36673, 29628,
     30117, 35160, 36930, 27839, 41590, 24203, 18321, 47980,
     50718, 15075,  9209, 57092,  4557, 60720, 62506,  2263,
     63512,  1253,  7679, 57602, 12235, 54070, 51756, 14033,
     19363, 46942, 44612, 21177, 40048, 24717, 31127, 34154,
     33651, 32654, 26260, 39529, 21664, 43101, 45383, 19898,
     12488, 52277, 54575, 10706, 59163,  7142,   764, 65025],
    [    0, 61681, 65023,  3342, 59363,  5906,  6684, 60141,
     54235,  9002, 11812, 57045, 13368, 50377, 51655, 14646,
     48043, 19290, 18004, 46757, 23624, 44217, 41399, 20806,
     26736, 39041, 38287, 25982, 36755, 32610, 29292, 33437,
     27467, 39866, 38580, 26181, 36008, 31833, 29015, 33190,
     47248, 18529, 17775, 46494, 24435, 44930, 41612, 21117,
     53472,  8209, 11551, 56814, 14083, 51186, 51964, 14861,
       827, 62410, 65220,  3637, 58584,  5161,  6439, 59862,
     54934,  9831, 11113, 56216, 12661, 49540, 52362, 15483,
      1357, 62908, 63666,  2115, 58030,  4703,  8017, 61344,
     27965, 40396, 37058, 24627, 35550, 31279, 30497, 34768,
     48870, 19991, 17177, 46056, 22789, 43508, 42234, 21515,
     48605, 19756, 16418, 45267, 23102, 43727, 42945, 22320,
     28166, 40695, 37881, 25352, 35301, 30996, 29722, 34027,
      1654, 63111, 64393,  2936, 57749,  4452,  7274, 60571,
     54701,  9564, 10322, 55459, 12878, 49855, 53169, 16192,
     45361, 16832, 19662, 48191, 22226, 42531, 43821, 23516,
     25322, 37403, 40725, 28644, 34057, 30200, 30966, 34823,
      2714, 64107, 63333,  1940, 60793,  7560,  4230, 57463,
     55617, 10672,  9406, 54351, 16034, 52819, 50013, 13228,
     55930, 10891, 10117, 55156, 15769, 52584, 49254, 12439,
      2465, 63824, 62558,  1199, 60994,  7859,  5053, 58188,
     25041, 37152, 39982, 27871, 34354, 30403, 31693, 35644,
     45578, 17147, 20469, 48900, 21993, 42264, 43030, 22759,
     26535, 38742, 39512, 27305, 32836, 28853, 32187, 36170,
     46204, 17549, 18819, 47474, 21407, 41838, 44640, 24209,
     56332, 11517,  8691, 53506, 15343, 51998, 50704, 14049,
      4055, 65318, 61992,   729, 59444,  6341,  5579, 58682,
      3308, 64541, 61715,   482, 60175,  7166,  5872, 58881,
     57143, 12230,  8904, 53817, 14548, 51237, 50475, 13786,
     46919, 18358, 19128, 47689, 20644, 41045, 44379, 23978,
     25756, 37997, 39267, 27026, 33663, 29582, 32384, 36465],
    [    0, 63223, 61939,  1796, 65531,  2316,  3592, 63743,
     58347,  5404,  4632, 58607,  7184, 60135, 60899,  6932,
     56267, 11580, 10808, 56527,  9264, 53959, 54723,  9012,
     14368, 52951, 51667, 16164, 51163, 12588, 13864, 49375,
     43915, 23932, 23160, 44175, 21616, 41607, 42371, 21364,
     18528, 48791, 47507, 20324, 47003, 16748, 18024, 45215,
     28736, 34487, 33203, 30532, 36795, 31052, 32328, 35007,
     37803, 25948, 25176, 38063, 27728, 39591, 40355, 27476,
     19211, 48636, 47864, 19471, 46320, 16903, 17667, 46068,
     43232, 24087, 22803, 45028, 22299, 41452, 42728, 20511,
     37056, 26167, 24883, 38852, 28475, 39372, 40648, 26687,
     29483, 34268, 33496, 29743, 36048, 31271, 32035, 35796,
     57472,  5751,  4467, 59268,  8059, 59788, 61064,  6271,
       875, 62876, 62104,  1135, 64656,  2663,  3427, 64404,
     15179, 52668, 51896, 15439, 50352, 12871, 13635, 50100,
     55456, 11863, 10579, 57252, 10075, 53676, 54952,  8287,
     38422, 24801, 26597, 37138, 27117, 40730, 38942, 28393,
     30205, 33546, 33806, 29433, 35334, 31985, 31733, 36098,
     19933, 47914, 48174, 19161, 45606, 17617, 17365, 46370,
     44598, 22721, 24517, 43314, 20941, 42810, 41022, 22217,
     15773, 52074, 52334, 15001, 49766, 13457, 13205, 50530,
     56950, 10369, 12165, 55666,  8589, 55162, 53374,  9865,
     58966,  4257,  6053, 57682,  6573, 61274, 59486,  7849,
      1469, 62282, 62542,   697, 64070,  3249,  2997, 64834,
     56605, 11242, 11502, 55833,  8934, 54289, 54037,  9698,
     16118, 51201, 52997, 14834, 49421, 14330, 12542, 50697,
      1750, 61473, 63269,   466, 63789,  4058,  2270, 65065,
     58685,  5066,  5326, 57913,  6854, 60465, 60213,  7618,
     30358, 32865, 34661, 29074, 35181, 32666, 30878, 36457,
     38269, 25482, 25742, 37497, 27270, 40049, 39797, 28034,
     44381, 23466, 23726, 43609, 21158, 42065, 41813, 21922,
     20150, 47169, 48965, 18866, 45389, 18362, 16574, 46665],
    [    0, 62964, 63477,   513, 62455,  1539,  1026, 61942,
     64499,  3591,  3078, 63986,  2052, 65008, 65521,  2565,
     60411,  7695,  7182, 59898,  6156, 60920, 61433,  6669,
      4104, 58876, 59389,  4617, 58367,  5643,  5130, 57854,
     52203, 15903, 15390, 51690, 14364, 52712, 53225, 14877,
     12312, 50668, 51181, 12825, 50159, 13851, 13338, 49646,
      8208, 54756, 55269,  8721, 54247,  9747,  9234, 53734,
     56291, 11799, 11286, 55778, 10260, 56800, 57313, 10773,
     35787, 32319, 31806, 35274, 30780, 36296, 36809, 31293,
     28728, 34252, 34765, 29241, 33743, 30267, 29754, 33230,
     24624, 38340, 38853, 25137, 37831, 26163, 25650, 37318,
     39875, 28215, 27702, 39362, 26676, 40384, 40897, 27189,
     16416, 46548, 47061, 16929, 46039, 17955, 17442, 45526,
     48083, 20007, 19494, 47570, 18468, 48592, 49105, 18981,
     43995, 24111, 23598, 43482, 22572, 44504, 45017, 23085,
     20520, 42460, 42973, 21033, 41951, 22059, 21546, 41438,
      2955, 65151, 64638,  2442, 63612,  3464,  3977, 64125,
     61560,  1420,  1933, 62073,   911, 63099, 62586,   398,
     57456,  5508,  6021, 57969,  4999, 58995, 58482,  4486,
      7043, 61047, 60534,  6530, 59508,  7552,  8065, 60021,
     49248, 13716, 14229, 49761, 13207, 50787, 50274, 12694,
     15251, 52839, 52326, 14738, 51300, 15760, 16273, 51813,
     11163, 56943, 56430, 10650, 55404, 11672, 12185, 55917,
     53352,  9628, 10141, 53865,  9119, 54891, 54378,  8606,
     32832, 30132, 30645, 33345, 29623, 34371, 33858, 29110,
     31667, 36423, 35910, 31154, 34884, 32176, 32689, 35397,
     27579, 40527, 40014, 27066, 38988, 28088, 28601, 39501,
     36936, 26044, 26557, 37449, 25535, 38475, 37962, 25022,
     19371, 48735, 48222, 18858, 47196, 19880, 20393, 47709,
     45144, 17836, 18349, 45657, 17327, 46683, 46170, 16814,
     41040, 21924, 22437, 41553, 21415, 42579, 42066, 20902,
     23459, 44631, 44118, 22946, 43092, 23968, 24481, 43605],
    [    0, 31355, 62710, 36493, 62961, 36746,   263, 31612,
     63487, 36228,   777, 31090,   526, 30837, 63224, 35971,
     62435, 35224,  1813, 32110,  1554, 31849, 62180, 34975,
      1052, 32359, 61674, 35473, 61933, 35734,  1307, 32608,
     64475, 33184,  3885, 30038,  3626, 29777, 64220, 32935,
      3108, 30303, 63698, 33449, 63957, 33710,  3363, 30552,
      2104, 29251, 64718, 34485, 64969, 34738,  2367, 29508,
     65479, 34236,  2865, 29002,  2614, 28749, 65216, 33979,
     60331, 37328,  8029, 25894,  7770, 25633, 60076, 37079,
      7252, 26159, 59554, 37593, 59813, 37854,  7507, 26408,
      6216, 25139, 60606, 38597, 60857, 38850,  6479, 25396,
     61367, 38348,  6977, 24890,  6726, 24637, 61104, 38091,
      4208, 27147, 58502, 40701, 58753, 40954,  4471, 27404,
     59279, 40436,  4985, 26882,  4734, 26629, 59016, 40179,
     58259, 39400,  5989, 27934,  5730, 27673, 58004, 39151,
      5228, 28183, 57498, 39649, 57757, 39910,  5483, 28432,
     52043, 45360, 16317, 17862, 16058, 17601, 51788, 45111,
     15540, 18127, 51266, 45625, 51525, 45886, 15795, 18376,
     14504, 17107, 52318, 46629, 52569, 46882, 14767, 17364,
     53079, 46380, 15265, 16858, 15014, 16605, 52816, 46123,
     12432, 19179, 50278, 48669, 50529, 48922, 12695, 19436,
     51055, 48404, 13209, 18914, 12958, 18661, 50792, 48147,
     50035, 47368, 14213, 19966, 13954, 19705, 49780, 47119,
     13452, 20215, 49274, 47617, 49533, 47878, 13707, 20464,
      8416, 23195, 54294, 44653, 54545, 44906,  8679, 23452,
     55071, 44388,  9193, 22930,  8942, 22677, 54808, 44131,
     54019, 43384, 10229, 23950,  9970, 23689, 53764, 43135,
      9468, 24199, 53258, 43633, 53517, 43894,  9723, 24448,
     56123, 41280, 12237, 21942, 11978, 21681, 55868, 41031,
     11460, 22207, 55346, 41545, 55605, 41806, 11715, 22456,
     10456, 21155, 56366, 42581, 56617, 42834, 10719, 21412,
     57127, 42332, 11217, 20906, 10966, 20653, 56864, 42075],
    [    0, 46002, 31609, 51403, 63218, 17728, 36235, 15929,
     61945, 16971, 35456, 14642,  1803, 46265, 31858, 53184,
     65519, 19549, 33942, 14116,  2333, 47791, 29284, 49622,
      3606, 48548, 30063, 50909, 63716, 19286, 33693, 12335,
     58307, 20593, 39098, 11016,  5425, 42627, 28232, 56826,
      4666, 41352, 26947, 56049, 58568, 22394, 40881, 11267,
      7212, 44958, 26453, 54503, 60126, 22892, 37287,  8725,
     60885, 24167, 38572,  9502,  6951, 43157, 24670, 54252,
     56219, 26665, 41186,  4944, 11625, 40667, 22032, 58786,
     10850, 39376, 20763, 58025, 56464, 28450, 42985,  5211,
      9332, 38854, 24333, 60607, 53894, 24884, 43519,  6733,
     54669, 26175, 44788,  7494,  9087, 37069, 22534, 60340,
     14424, 35818, 17185, 61587, 52906, 32024, 46547,  1633,
     51617, 31251, 45784,   362, 16211, 36065, 17450, 63384,
     51127, 29701, 48334,  3964, 12613, 33527, 19004, 63886,
     13902, 34300, 19767, 65157, 49340, 29454, 48069,  2167,
     43819,  6297, 53330, 25568, 24025, 61035,  9888, 38162,
     23250, 59744,  8619, 37401, 44064,  8082, 55129, 25835,
     21700, 59254, 12221, 39951, 41526,  4484, 55631, 27389,
     42301,  5775, 56900, 28150, 21455, 57469, 10422, 39684,
     18664, 64346, 13201, 32803, 48666,  3496, 50531, 30417,
     47377,  2723, 49768, 29146, 20451, 64593, 13466, 34600,
     46855,  1205, 52350, 32716, 16885, 62023, 14988, 35134,
     18174, 62796, 15751, 36405, 45068,   958, 52085, 30919,
     28848, 49922,  3017, 47227, 34370, 13808, 64827, 20105,
     33097, 13051, 64048, 18818, 30651, 50185,  3266, 49008,
     36703, 15597, 62502, 18324, 31149, 51743,   724, 45414,
     32422, 52500,  1503, 46701, 34900, 15334, 62253, 16543,
     37747,  8385, 59402, 23480, 25985, 54835,  7928, 44362,
     25226, 53560,  6643, 43585, 38008, 10186, 61185, 23731,
     27804, 57134,  6117, 42071, 39534, 10716, 57623, 21157,
     40293, 11991, 58908, 21934, 27543, 55333,  4334, 41820],
    [    0, 22872, 45744, 60392, 31101,  8229, 52173, 37525,
     62202, 43938, 16458,  6418, 35719, 53983, 14647, 24687,
     63977, 41137, 19289,  4609, 32916, 55756, 12836, 27516,
      2835, 21067, 47523, 57595, 29294, 11062, 49374, 39302,
     61391, 46743, 23935,  1063, 38578, 53226,  9218, 32090,
      7477, 17517, 44933, 63197, 25672, 15632, 55032, 36768,
      5670, 20350, 42134, 64974, 28507, 13827, 56811, 33971,
     58588, 48516, 22124,  3892, 40353, 50425, 12049, 30281,
     50051, 39643, 28979, 10347, 47870, 58278,  2126, 20758,
     12665, 26657, 33737, 55953, 18436,  4444, 64180, 41964,
     14954, 25394, 35034, 53634, 17175,  6735, 61863, 43263,
     51344, 37320, 31264,  9080, 45549, 59573,   861, 23045,
     11340, 29972, 40700, 51108, 21809,  3177, 59265, 48857,
     57014, 34798, 27654, 13662, 42955, 65171,  5499, 19491,
     54693, 36093, 26389, 15949, 44248, 62848,  7784, 18224,
     10079, 32263, 38383, 52407, 24098,  1914, 60562, 46538,
     39707, 49731, 10667, 28915, 57958, 47934, 20694,  2446,
     27105, 12473, 56145, 33289,  4252, 18884, 41516, 64372,
     25330, 15274, 53314, 35098,  7055, 17111, 43327, 61543,
     36872, 51536,  8888, 31712, 59765, 45101, 23493,   669,
     29908, 11660, 50788, 40764,  3497, 21745, 48921, 58945,
     34350, 57206, 13470, 28102, 65363, 42507, 19939,  5307,
     36157, 54373, 16269, 26325, 62528, 44312, 18160,  8104,
     32711,  9887, 52599, 37935,  1722, 24546, 46090, 60754,
     22680,   448, 59944, 45936,  8677, 30909, 37717, 51725,
     43618, 62266,  6354, 16778, 54047, 35399, 25007, 14583,
     41329, 63529,  5057, 19097, 55308, 33108, 27324, 13284,
     21387,  2771, 57659, 47203, 10998, 29614, 38982, 49438,
     46935, 60943,  1511, 23743, 52778, 38770, 31898,  9666,
     17837,  7413, 63261, 44613, 15568, 25992, 36448, 55096,
     20158,  6118, 64526, 42326, 14275, 28315, 34163, 56363,
     48196, 58652,  3828, 22444, 50489, 40033, 30601, 11985],
    [    0, 11309, 22618, 29815, 45236, 40089, 59630, 50371,
     32117, 20824,  9519,  2306, 52673, 57836, 38299, 47542,
     64234, 54983, 41648, 36509, 19038, 26227,  4612, 15913,
     34719, 43954, 57285, 62440, 14123,  6918, 28529, 17244,
     59849, 50660, 45459, 40382, 22909, 30032,   295, 11530,
     38076, 47249, 52454, 57547,  9224,  2085, 31826, 20607,
      4899, 16142, 19321, 26452, 41879, 36794, 64461, 55264,
     28246, 17019, 13836,  6689, 57058, 62159, 34488, 43669,
     53135, 58274, 38869, 48120, 32571, 21270, 10081,  2892,
     45818, 40663, 60064, 50829,   590, 11875, 23060, 30265,
     13669,  6472, 27967, 16658, 34257, 43516, 56715, 61862,
     18448, 25661,  4170, 15463, 63652, 54409, 41214, 36051,
      9798,  2667, 32284, 21041, 38642, 47839, 52904, 57989,
     23347, 30494,   873, 12100, 60295, 51114, 46045, 40944,
     56492, 61569, 34038, 43227, 27672, 16437, 13378,  6255,
     41433, 36340, 63875, 54702,  4461, 15680, 18743, 25882,
     33539, 44846, 56153, 63348, 13239,  8090, 27629, 18368,
     65142, 53851, 42540, 35329, 20162, 25327,  5784, 15029,
     31209, 21956,  8627,  3486, 51549, 58736, 37127, 48426,
      1180, 10417, 23750, 28907, 46120, 38917, 60530, 49247,
     27338, 18151, 12944,  7869, 55934, 63059, 33316, 44553,
      6079, 15250, 20453, 25544, 42763, 35622, 65361, 54140,
     36896, 48141, 51322, 58455,  8340,  3257, 30926, 21731,
     60757, 49528, 46351, 39202, 24033, 29132,  1467, 10646,
     19596, 24737,  5334, 14587, 64568, 53269, 42082, 34895,
     12793,  7636, 27043, 17806, 33101, 44384, 55575, 62778,
     46694, 39499, 60988, 49681,  1746, 11007, 24200, 29349,
     51987, 59198, 37705, 48996, 31655, 22410,  9213,  4048,
     42309, 35176, 64799, 53554,  5617, 14812, 19883, 24966,
     55344, 62493, 32874, 44103, 26756, 17577, 12510,  7411,
     24495, 29570,  2037, 11224, 61211, 49974, 46913, 39788,
      8922,  3831, 31360, 22189, 37486, 48707, 51764, 58905],
    [    0, 39065, 11567, 46518, 23134, 49863, 30577, 61416,
     46268, 11301, 39315,   266, 61154, 30331, 50125, 23380,
     30053, 60924, 22602, 49363, 12091, 47010,   532, 39565,
     49625, 22848, 60662, 29807, 39815,   798, 46760, 11825,
     60106, 29267, 51173, 24444, 45204, 10253, 40379,  1314,
     24182, 50927, 29529, 60352,  1064, 40113, 10503, 45470,
     40879,  1846, 45696, 10777, 50673, 23912, 59614, 28743,
     11027, 45962,  1596, 40613, 29005, 59860, 23650, 50427,
     51593, 20752, 58534, 31807, 37847,  2894, 48888,  9825,
     32053, 58796, 20506, 51331, 10091, 49138,  2628, 37597,
     48364,  9333, 37315,  2394, 59058, 32299, 52125, 21252,
      2128, 37065,  9599, 48614, 21006, 51863, 32545, 59320,
      9027, 48090,  3692, 38645, 31005, 57732, 21554, 52395,
     38911,  3942, 47824,  8777, 52641, 21816, 57486, 30743,
     22054, 52927, 31497, 58256,  3192, 38113,  8535, 47566,
     58010, 31235, 53173, 22316, 47300,  8285, 38379,  3442,
     36623,  6038, 41504, 15033, 54609, 19912, 63614, 24807,
     15283, 41770,  5788, 36357, 25069, 63860, 19650, 54363,
     64106, 25331, 55109, 20444, 41012, 14509, 36123,  5506,
     20182, 54863, 25593, 64352,  5256, 35857, 14759, 41278,
     26053, 64860, 18666, 53363, 16283, 42754,  4788, 35373,
     53625, 18912, 64598, 25807, 35623,  5054, 42504, 16017,
      4256, 34873, 15759, 42262, 19198, 53863, 26577, 65352,
     42012, 15493, 35123,  4522, 65090, 26331, 54125, 19444,
     18054, 56863, 27561, 62256,  7384, 33857, 12791, 43374,
     62010, 27299, 57109, 18316, 43108, 12541, 34123,  7634,
     13283, 43898,  7884, 34389, 27069, 61732, 17554, 56331,
     34655,  8134, 43632, 13033, 56577, 17816, 61486, 26807,
     44108, 13525, 33123,  6650, 62994, 28299, 56125, 17316,
      6384, 32873, 13791, 44358, 17070, 55863, 28545, 63256,
     55593, 16816, 62470, 27807, 33655,  7150, 44632, 14017,
     28053, 62732, 16570, 55331, 14283, 44882,  6884, 33405],
    [    0, 49859, 39323, 23384, 12075, 60904, 46768, 29811,
     24150, 40085, 51149,  1294, 29053, 46014, 59622, 10789,
     48300, 32367,  9527, 59380, 37767, 20804,  2588, 51423,
     58106,  8249, 31585, 47522, 52689,  3858, 21578, 38537,
     25925, 42886, 64734, 15901, 19054, 34989, 54261,  4406,
     15123, 63952, 41608, 24651,  5176, 55035, 36259, 20320,
     55785,  6954, 16498, 33457, 63170, 13313, 28505, 44442,
     34751, 17788,  7716, 56551, 43156, 27223, 12559, 62412,
     51850,  2121, 21265, 37330, 58785, 10082, 31802, 48889,
     38108, 22047,  3399, 53124, 48119, 31028,  8812, 57519,
     30246, 46309, 61373, 11646, 22797, 39886, 49302,   597,
     10352, 60083, 45547, 29480,  1883, 50584, 40640, 23555,
     45007, 27916, 13908, 62615, 32996, 16935,  6527, 56252,
     61849, 13146, 26626, 43713, 57010,  7281, 18217, 34282,
      4963, 53664, 35576, 18491, 15432, 65163, 42451, 26384,
     19765, 36854, 54446,  5741, 25118, 41181, 64389, 14662,
     35081, 19402,  4242, 53841, 42530, 25825, 16313, 64890,
     55135,  5532, 20164, 35847, 63604, 15031, 25071, 41772,
     13733, 63334, 44094, 28413,  6798, 55373, 33557, 16854,
     27635, 43312, 62056, 12459, 17624, 34331, 56643,  8064,
     60492, 11919, 30167, 46868, 50023,   420, 23292, 38975,
     45594, 28889, 11137, 59714, 40241, 24562,  1194, 50793,
     20704, 37411, 51579,  3000, 32715, 48392, 58960,  9363,
      3766, 52341, 38701, 21998,  8605, 58206, 47110, 31429,
     17283, 33088, 55832,  6363, 27816, 44651, 62771, 14320,
      7637, 57110, 33870, 18061, 13054, 61501, 43877, 27046,
     65327, 15852, 26292, 42103, 53252,  4807, 18847, 35676,
     41337, 25530, 14562, 64033, 36434, 19601,  6089, 54538,
      9926, 58373, 48989, 32158,  2541, 52014, 36982, 21173,
     30864, 47699, 57611,  9160, 22459, 38264, 52768,  3299,
     39530, 22697,  1009, 49458, 46401, 30594, 11482, 60953,
     50236,  1791, 23975, 40804, 60183, 10708, 29324, 45135],
    [    0, 61422, 50113, 11311, 39839, 29809, 22622, 47024,
     11043, 50381, 59618,  1804, 45244, 24402, 29565, 40083,
     22086, 47528, 38279, 31337, 52697,  8759,  3608, 57846,
     32101, 37515, 48804, 20810, 59130,  2324,  9531, 51925,
     44172, 17250, 28493, 32931, 14099, 55549, 62674,  6972,
     34735, 26689, 17518, 43904,  7216, 62430, 57329, 12319,
     64202,  5412, 14603, 55013, 24917, 36539, 41620, 19834,
     53737, 15879,  4648, 64966, 19062, 42392, 35255, 26201,
     17669, 43755, 34500, 26922, 56986, 12660,  7515, 62133,
     28198, 33224, 44519, 16905, 62905,  6743, 13944, 55702,
      4931, 64685, 53378, 16236, 35036, 26418, 19229, 42227,
     14432, 55182, 64417,  5199, 41983, 19473, 24638, 36816,
     59785,  1639, 10824, 50598, 29206, 40440, 45527, 24121,
     49834, 11588,   363, 61061, 22837, 46811, 39668, 29978,
     49103, 20513, 31758, 37856,  9296, 52158, 59281,  2175,
     38124, 31490, 22317, 47299,  3955, 57501, 52402,  9052,
     35338, 26084, 18891, 42533,  4501, 65147, 53844, 15802,
     41257, 20167, 25320, 36102, 15030, 54616, 63863,  5785,
     56396, 13218,  8077, 61539, 18387, 43069, 33810, 27644,
     63343,  6273, 13486, 56128, 27888, 33566, 44849, 16607,
      9862, 51560, 58695,  2729, 48409, 21239, 32472, 37174,
      3493, 57931, 52836,  8586, 38458, 31188, 22011, 47637,
     28864, 40750, 45825, 23791, 60255,  1201, 10398, 51056,
     23523, 46093, 38946, 30668, 49276, 12178,   957, 60499,
     53007,  8417,  3278, 58144, 21648, 47998, 38737, 30911,
     58412,  3010, 10221, 51203, 32691, 36957, 48242, 21404,
     39241, 30375, 23176, 46438,   726, 60728, 49431, 12025,
     45674, 23940, 29099, 40517, 10741, 50715, 59956,  1498,
     25475, 35949, 41026, 20396, 63516,  6130, 15325, 54323,
     18592, 42830, 35681, 25743, 54079, 15569,  4350, 65296,
     13765, 55851, 62980,  6634, 44634, 16820, 28059, 33397,
      7910, 61704, 56615, 13001, 34169, 27287, 18104, 43350],
    [    0, 30582, 61164, 39322, 49605, 46771, 12073, 22623,
     40855, 59617, 29051,  1549, 24146, 10532, 45246, 51144,
      9011, 21573, 52703, 47785, 58102, 38272,  3098, 31596,
     48292, 52178, 21064,  9534, 32097,  2583, 37773, 58619,
     18022, 12560, 43146, 57340, 34723, 61653, 26959,  7737,
     55793, 44679, 14109, 16491,  6196, 28482, 63192, 33198,
     25941,  4643, 35769, 64719, 42128, 54246, 19068, 15626,
     64194, 36276,  5166, 25432, 15111, 19569, 54763, 41629,
     36044, 64442, 25120,  5462, 19721, 14975, 41957, 54419,
      4955, 25645, 64951, 35521, 53918, 42472, 15474, 19204,
     45055, 55433, 16659, 13925, 28218,  6476, 32982, 63392,
     12392, 18206, 56964, 43506, 61869, 34523,  8001, 26679,
     51882, 48604,  9286, 21296,  2927, 31769, 58755, 37621,
     21821,  8779, 48081, 52391, 38136, 58254, 31252,  3426,
     59801, 40687,  1909, 28675, 10332, 24362, 50864, 45510,
     30222,   376, 39138, 61332, 47051, 49341, 22823, 11857,
      1413, 29427, 60265, 39967, 50240, 45878, 10924, 24026,
     39442, 60772, 29950,   904, 23511, 11425, 46395, 49741,
      9910, 20928, 51290, 48940, 59251, 36869,  2463, 32489,
     47393, 52823, 22477,  8379, 30948,  3986, 38408, 57726,
     17379, 13461, 44303, 55929, 33318, 62800, 27850,  7100,
     56436, 43778, 12952, 17902,  7601, 27335, 62301, 33835,
     24784,  6054, 36412, 63818, 41237, 54883, 20473, 14479,
     65351, 34865,  4523, 26333, 16002, 18932, 53358, 42776,
     35145, 65087, 26533,  4307, 18572, 16378, 42592, 53526,
      5854, 25000, 63538, 36676, 55067, 41069, 14839, 20097,
     43642, 56588, 17558, 13280, 27583,  7369, 34131, 61989,
     13805, 17051, 56065, 44151, 62504, 33630,  6852, 28082,
     53039, 47193,  8643, 22197,  3818, 31132, 57350, 38768,
     20664, 10190, 48724, 51490, 37245, 58891, 32657,  2279,
     60444, 39786,   752, 30086, 11737, 23215, 49973, 46147,
     29579,  1277, 40295, 59921, 45646, 50488, 23714, 11220],
    [    0, 15162, 30324, 19790, 60648, 55250, 39580, 41382,
     50637, 65271, 46009, 34947, 10533,  4639, 24401, 25707,
     38791, 44221, 57843, 56009, 31599, 16469,  3355, 13857,
     21066, 26992,  9278,  7940, 48802, 34200, 51414, 62444,
     13075,  2089, 17767, 32349, 57339, 58561, 43407, 37557,
     63198, 52708, 32938, 48016,  6710,  8460, 27714, 22392,
     42132, 40878, 53984, 59866, 18556, 29510, 15880,  1330,
     24921, 23139,  5933, 11287, 36273, 46731, 64453, 49407,
     26150, 23836,  4178, 11112, 35534, 45556, 64698, 51072,
     41963, 39121, 54687, 61093, 20227, 29753, 14711,   589,
     61857, 51867, 34773, 48367,  7497,  9843, 27453, 20487,
     13420,  3926, 16920, 31010, 55428, 58302, 44784, 38346,
     21813, 28175,  9025,  6267, 47581, 33511, 53161, 62611,
     37112, 43970, 59020, 56758, 31760, 18218,  2660, 12638,
     49842, 63880, 46278, 36860, 11866,  5472, 22574, 25364,
      1919, 15429, 28939, 18993, 60311, 53421, 40419, 42713,
     52300, 63350, 47672, 33026,  8356,  7070, 22224, 28138,
      2433, 12987, 32757, 17615, 58729, 56915, 37661, 43047,
     23499, 24817, 11711,  5765, 46883, 35865, 49495, 64109,
     40454, 42300, 59506, 54088, 29422, 18900,  1178, 16288,
     65375, 50277, 35115, 45585,  5047, 10381, 26051, 24313,
     14994,   424, 19686, 30684, 54906, 60736, 40974, 39732,
     26840, 21474,  7852,  9622, 33840, 48906, 62020, 51582,
     44309, 38447, 56161, 57435, 16893, 31431, 14217,  3251,
     43626, 37200, 56350, 59172, 18050, 32184, 12534,  3020,
     28583, 21661,  6611,  8937, 33615, 47221, 62779, 52737,
     15853,  1751, 19353, 28835, 53509, 59967, 42865, 40011,
     63520, 49946, 36436, 46446,  5320, 12274, 25276, 22918,
     39289, 41539, 61197, 54327, 30097, 20139,   997, 14559,
     23732, 26510, 10944,  4602, 45148, 35686, 50728, 64786,
      3838, 13764, 30858, 17328, 57878, 55596, 37986, 44888,
     52019, 61449, 48455, 34429, 10203,  7393, 20911, 27285],
    [    0,  7452, 14904, 10020, 29808, 26988, 20040, 21332,
     59616, 62972, 53976, 53188, 40080, 33164, 42664, 48052,
     52701, 53441, 63461, 60153, 47533, 42161, 33685, 40585,
      9533, 14369,  7941,   537, 20813, 19537, 27509, 30313,
     34727, 39611, 48543, 41091, 62423, 61131, 51695, 54515,
     28487, 29275, 21887, 18531,  6967,  1579,  8463, 15379,
     19066, 22374, 28738, 27998, 15882,  8982,  1074,  6446,
     41626, 49030, 39074, 34238, 55018, 52214, 60626, 61902,
      4947,  3663, 10603, 13431, 26403, 31295, 23835, 16391,
     64435, 59055, 49547, 56471, 36803, 37599, 46587, 43239,
     56974, 50066, 58550, 63914, 43774, 47074, 37062, 36314,
     13934, 11122,  3158,  4426, 16926, 24322, 30758, 25914,
     38132, 35304, 44748, 46032, 57476, 64920, 55996, 51104,
     31764, 24840, 17964, 23344,  2148,  5496, 12892, 12096,
     22825, 17461, 25361, 32269, 11609, 12357,  5985,  2685,
     45513, 44245, 35825, 38637, 50617, 55461, 65409, 58013,
      9894, 15290,  7326,   386, 21206, 20426, 26862, 30194,
     52806, 54106, 62590, 59746, 47670, 42794, 32782, 40210,
     60283, 63079, 53571, 52319, 40715, 33303, 42291, 47151,
       923,  7815, 14755,  9407, 30699, 27383, 19923, 20687,
     41217, 48157, 39737, 34341, 54641, 51309, 61257, 62037,
     18913, 21757, 29657, 28357, 15761,  8333,  1961,  6837,
     27868, 29120, 22244, 19448,  6316,  1456,  8852, 16264,
     33852, 39200, 48644, 41752, 61516, 60752, 51828, 55144,
     13813, 10473,  4045,  4817, 16773, 23705, 31677, 26273,
     56597, 49161, 59181, 64049, 43365, 46201, 37725, 36417,
     63528, 58676, 49680, 57100, 35928, 37188, 46688, 43900,
      4296,  3540, 10992, 14316, 25784, 31140, 24192, 17308,
     45650, 44878, 34922, 38262, 50722, 56126, 64538, 57606,
     23218, 18350, 24714, 32150, 11970, 13278,  5370,  2534,
     32655, 25235, 17847, 22699,  3071,  5859, 12743, 11483,
     38767, 35443, 44375, 45131, 58143, 65027, 55591, 50235],
    [    0,  3599,  7198,  4625, 14396, 13875,  9250, 10797,
     28792, 32375, 27750, 25193, 18500, 17995, 21594, 23125,
     57584, 61183, 64750, 62177, 55500, 54979, 50386, 51933,
     37000, 40583, 35990, 33433, 43188, 42683, 46250, 47781,
     56829, 54258, 49635, 53228, 58817, 60366, 63967, 63440,
     44421, 41866, 45467, 49044, 38329, 39862, 35239, 34728,
     15629, 13058,  8467, 12060,  1329,  2878,  6447,  5920,
     19829, 17274, 20843, 24420, 30025, 31558, 26967, 26456,
     42983, 43496, 48121, 46582, 40923, 37332, 33733, 36298,
     55199, 55696, 52097, 50574, 61347, 57772, 62397, 64946,
     18199, 18712, 23305, 21766, 32555, 28964, 25397, 27962,
     14191, 14688, 11121,  9598,  3923,   348,  4941,  7490,
     31258, 29717, 26116, 26635, 16934, 19497, 24120, 20535,
      2658,  1133,  5756,  6259, 12894, 15441, 11840,  8271,
     39658, 38117, 34548, 35067, 41686, 44249, 48840, 45255,
     60050, 58525, 63116, 63619, 53934, 56481, 52912, 49343,
     21459, 24028, 20429, 16834, 27631, 26080, 30705, 31230,
      9131, 11684, 16309, 12730,  7063,  5528,  1929,  2438,
     45859, 48428, 44861, 41266, 35615, 34064, 38657, 39182,
     50011, 52564, 57157, 53578, 64359, 62824, 59257, 59766,
     36398, 32801, 37424, 39999, 46610, 47133, 43532, 41987,
     65110, 61529, 57928, 60487, 50794, 51301, 55924, 54395,
     28382, 24785, 29376, 31951, 22242, 22765, 19196, 17651,
      7846,  4265,   696,  3255,  9882, 10389, 14980, 13451,
     62516, 64059, 59434, 58917, 52232, 49671, 53270, 56857,
     33868, 35395, 38994, 38493, 48240, 45695, 41070, 44641,
      5316,  6859,  2266,  1749, 11512,  8951, 12518, 16105,
     25788, 27315, 30882, 30381, 23680, 21135, 16542, 20113,
     10697, 10182, 13783, 15320,  4597,  8186,  3563,   996,
     22961, 22462, 17839, 19360, 24973, 28546, 32147, 29596,
     51513, 50998, 54567, 56104, 61701, 65290, 60699, 58132,
     47425, 46926, 42335, 43856, 33149, 36722, 40291, 37740],
    [    0, 35208,  3853, 34437,  7706, 38802,  4375, 39071,
     15412, 46524, 13113, 47793,  8750, 43942, 11555, 42155,
     30824, 61920, 30565, 65261, 26226, 61434, 27007, 57591,
     17500, 52692, 19281, 49881, 23110, 54222, 21835, 56515,
     61648, 31064, 65501, 30293, 61130, 26434, 57799, 26703,
     52452, 17772, 50153, 19041, 54014, 23414, 56819, 21627,
     35000,   304, 34741,  3645, 38562,  7978, 39343,  4135,
     46220, 15620, 48001, 12809, 43670,  8990, 42395, 11283,
     64957, 29749, 62128, 31544, 58279, 27183, 60586, 25890,
     49545, 18433, 52868, 18188, 57235, 22043, 53406, 22806,
     34261,  3165, 35544,   848, 39887,  4679, 38082,  7498,
     47585, 12393, 46828, 16228, 43003, 11891, 43254,  8574,
      3437, 34021,   608, 35816,  4983, 39679,  7290, 38386,
     12633, 47313, 15956, 47068, 12099, 42699,  8270, 43462,
     29957, 64653, 31240, 62336, 27423, 58007, 25618, 60826,
     18737, 49337, 17980, 53172, 22315, 56995, 22566, 53678,
     59239, 28399, 59498, 25058, 63869, 28917, 63088, 32760,
     56147, 21211, 54366, 24022, 50505, 19649, 51780, 17356,
     40719,  5767, 36866,  6538, 33045,  2205, 36376,  1936,
     41787, 10931, 44086,  9662, 48417, 13481, 45612, 15268,
      6071, 40511,  6330, 37170,  2477, 32805,  1696, 36648,
     11139, 41483,  9358, 44294, 13721, 48145, 14996, 45852,
     28639, 58967, 24786, 59738, 29125, 63565, 32456, 63296,
     21483, 55907, 23782, 54638, 19953, 50297, 17148, 52084,
      6874, 37714,  5591, 40031,  1216, 36168,  3021, 33349,
      9966, 44902, 10723, 41067, 14580, 45436, 14329, 48753,
     25266, 60218, 28095, 58423, 31912, 62752, 29605, 64045,
     24198, 55054, 20875, 55299, 16540, 51476, 20369, 50713,
     59914, 25474, 58631, 27791, 62480, 32152, 64285, 29333,
     54846, 24502, 55603, 20667, 51236, 16812, 50985, 20129,
     37474,  7146, 40303,  5351, 35960,  1520, 33653,  2813,
     44630, 10206, 41307, 10451, 45132, 14788, 48961, 14025],
    [    0, 17477, 34954, 52431,  3337, 18764, 34179, 49606,
      6674, 24151, 37528, 55005,  5915, 21342, 40849, 56276,
     13348, 28769, 48302, 63723, 14637, 32104, 45479, 62946,
     11830, 27251, 42684, 58105,  9023, 26490, 43957, 61424,
     26696, 11277, 57538, 42119, 25921,  8452, 60875, 43406,
     29274, 13855, 64208, 48789, 32595, 15126, 63449, 45980,
     23660,  6185, 54502, 37027, 20837,  5408, 55791, 40362,
     18046,   571, 52980, 35505, 19319,  3890, 50173, 34744,
     53392, 38101, 22554,  7263, 56729, 39388, 21779,  4438,
     51842, 36551, 16904,  1613, 51083, 33742, 20225,  2884,
     58548, 41201, 27710, 10363, 59837, 44536, 24887,  9586,
     65190, 47843, 30252, 12905, 62383, 47082, 31525, 16224,
     47320, 64669, 12370, 29719, 46545, 61844, 15707, 31006,
     41674, 59023, 10816, 28165, 44995, 60294, 10057, 25356,
     36092, 51385,  1142, 16435, 33269, 50608,  2431, 19770,
     38638, 53931,  7780, 23073, 39911, 57250,  4973, 22312,
     48445, 63864, 13751, 29170, 45108, 62577, 14526, 31995,
     42799, 58218, 12197, 27616, 43558, 61027,  8876, 26345,
     35097, 52572,   403, 17878, 33808, 49237,  3226, 18655,
     37643, 55118,  7041, 24516, 40450, 55879,  5768, 21197,
     54645, 37168, 24063,  6586, 55420, 39993, 20726,  5299,
     53095, 35618, 18413,   936, 49774, 34347, 19172,  3745,
     57681, 42260, 27099, 11678, 60504, 43037, 25810,  8343,
     64323, 48902, 29641, 14220, 63050, 45583, 32448, 14981,
     28077, 10728, 58663, 41314, 24740,  9441, 59438, 44139,
     30655, 13306, 65333, 47984, 31414, 16115, 62012, 46713,
     22921,  7628, 53507, 38214, 21632,  4293, 56330, 38991,
     17307,  2014, 51985, 36692, 20114,  2775, 50712, 33373,
      1509, 16800, 36207, 51498,  2284, 19625, 32870, 50211,
      8183, 23474, 38781, 54072,  4862, 22203, 39540, 56881,
     12737, 30084, 47435, 64782, 15560, 30861, 46146, 61447,
     11219, 28566, 41817, 59164,  9946, 25247, 44624, 59925],
    [    0, 44205, 17735, 59882, 35470,  9763, 53193, 25444,
      2305, 42412, 19526, 57579, 33679, 12066, 50888, 27237,
      4610, 48815, 22341, 64488, 39052, 13345, 56779, 29030,
      6915, 47022, 24132, 62185, 37261, 15648, 54474, 30823,
      9220, 34985, 24899, 52718, 44682,   551, 60365, 18272,
     11525, 33192, 26690, 50415, 42891,  2854, 58060, 20065,
     13830, 39595, 29505, 57324, 48264,  4133, 63951, 21858,
     16135, 37802, 31296, 55021, 46473,  6436, 61646, 23651,
     18440, 58533,  3407, 41442, 49798, 28203, 34753, 11116,
     16649, 60836,  1102, 43235, 52103, 26410, 36544,  8813,
     23050, 63143,  8013, 46048, 53380, 31785, 38339, 14702,
     21259, 65446,  5708, 47841, 55685, 29992, 40130, 12399,
     27660, 49313, 10571, 34278, 59010, 18991, 41925,  3944,
     25869, 51616,  8266, 36071, 61315, 17198, 43716,  1641,
     32270, 53923, 15177, 38884, 62592, 22573, 45511,  7530,
     30479, 56226, 12872, 40677, 64897, 20780, 47302,  5227,
     36880, 15549, 54615, 31226,  6814, 46643, 24537, 62324,
     39185, 13756, 56406, 28923,  5023, 48946, 22232, 64117,
     33298, 11967, 51029, 27640,  2204, 42033, 19931, 57718,
     35603, 10174, 52820, 25337,   413, 44336, 17626, 59511,
     46100,  6329, 61779, 24062, 16026, 37431, 31709, 55152,
     48405,  4536, 63570, 21759, 14235, 39734, 29404, 56945,
     42518,  2747, 58193, 20476, 11416, 32821, 27103, 50546,
     44823,   954, 59984, 18173,  9625, 35124, 24798, 52339,
     55320, 29877, 40287, 12786, 21142, 65083,  6097, 47996,
     53529, 32180, 37982, 14579, 23447, 63290,  7888, 45693,
     51738, 26295, 36701,  9200, 16532, 60473,  1491, 43390,
     49947, 28598, 34396, 10993, 18837, 58680,  3282, 41087,
     64540, 20657, 47451,  5622, 30354, 55871, 13269, 40824,
     62749, 22960, 45146,  7415, 32659, 54078, 15060, 38521,
     60958, 17075, 43865,  2036, 25744, 51261,  8663, 36218,
     59167, 19378, 41560,  3829, 28049, 49468, 10454, 33915],
    [    0, 55513, 44463, 30070, 18243, 40858, 60140, 12853,
     36486, 22111,  9001, 64496, 51653,  4380, 25706, 48307,
       273, 55752, 44222, 29799, 18002, 40587, 60413, 13092,
     36759, 22350,  8760, 64225, 51412,  4109, 25979, 48546,
       546, 56059, 44941, 30548, 17761, 40376, 59598, 12311,
     36004, 21629,  8459, 63954, 52199,  4926, 26184, 48785,
       819, 56298, 44700, 30277, 17520, 40105, 59871, 12550,
     36277, 21868,  8218, 63683, 51958,  4655, 26457, 49024,
      1092, 56477, 43499, 28978, 17159, 39902, 61096, 13937,
     35522, 21019, 10093, 65460, 52609,  5464, 24622, 47351,
      1365, 56716, 43258, 28707, 16918, 39631, 61369, 14176,
     35795, 21258,  9852, 65189, 52368,  5193, 24895, 47590,
      1638, 57023, 43977, 29456, 16677, 39420, 60554, 13395,
     35040, 20537,  9551, 64918, 53155,  6010, 25100, 47829,
      1911, 57262, 43736, 29185, 16436, 39149, 60827, 13634,
     35313, 20776,  9310, 64647, 52914,  5739, 25373, 48068,
      2184, 53329, 42279, 32254, 20427, 38674, 57956, 15037,
     34318, 24279, 11169, 62328, 49485,  6548, 27874, 46139,
      2457, 53568, 42038, 31983, 20186, 38403, 58229, 15276,
     34591, 24518, 10928, 62057, 49244,  6277, 28147, 46378,
      2730, 53875, 42757, 32732, 19945, 38192, 57414, 14495,
     33836, 23797, 10627, 61786, 50031,  7094, 28352, 46617,
      3003, 54114, 42516, 32461, 19704, 37921, 57687, 14734,
     34109, 24036, 10386, 61515, 49790,  6823, 28625, 46856,
      3276, 54293, 41315, 31162, 19343, 37718, 58912, 16121,
     33354, 23187, 12261, 63292, 50441,  7632, 26790, 45183,
      3549, 54532, 41074, 30891, 19102, 37447, 59185, 16360,
     33627, 23426, 12020, 63021, 50200,  7361, 27063, 45422,
      3822, 54839, 41793, 31640, 18861, 37236, 58370, 15579,
     32872, 22705, 11719, 62750, 50987,  8178, 27268, 45661,
      4095, 55078, 41552, 31369, 18620, 36965, 58643, 15818,
     33145, 22944, 11478, 62479, 50746,  7907, 27541, 45900],
    [    0, 58083, 55771, 15160, 44971, 19784, 30320, 38035,
     17227, 41384, 39568, 30835, 60640,  3587, 13627, 55256,
     34454, 25717, 24397, 48558, 10557, 52190, 61670,  4613,
     50653, 10046,  7174, 65253, 27254, 34965, 45997, 20814,
      4401, 62418, 51434, 10761, 48794, 23673, 26433, 34210,
     21114, 45209, 35745, 26946, 64977,  7986,  9226, 50921,
     38823, 30020, 20092, 44191, 14348, 56047, 57815,   820,
     54508, 13839,  3383, 61396, 31559, 39332, 41628, 16511,
      8802, 49281, 64441,  6490, 36297, 28458, 21522, 46833,
     24873, 33738, 47346, 23057, 52866, 11361,  5977, 62906,
     42228, 17943, 32047, 40908,  2911, 59836, 53892, 12391,
     59327,  1372, 15972, 56455, 18452, 43767, 37327, 29484,
     13139, 53680, 60040,  2155, 40184, 32283, 17699, 42944,
     28696, 37627, 43459, 19232, 57267, 15696,  1640, 58507,
     46533, 22310, 27678, 36605,  6766, 63629, 50101,  8534,
     63118,  5229, 12117, 52662, 22821, 48070, 33022, 25117,
     17604, 42535, 40223, 32764, 60271,  2444, 12980, 53335,
      1935, 58732, 56916, 15543, 43044, 19143, 29183, 37660,
     49746,  8369,  7049, 63850, 28153, 36634, 46114, 22209,
     33049, 25594, 22722, 47649, 11954, 52305, 63337,  5514,
     22005, 46870, 35886, 28365, 64094,  6333,  9093, 49510,
      5822, 62557, 53093, 11654, 47381, 23542, 24782, 33325,
     54115, 12672,  2744, 59483, 31944, 40491, 42259, 18416,
     36904, 29387, 18931, 43792, 16259, 56672, 58968,  1211,
     26278, 33861, 49021, 23966, 51469, 11246,  4310, 62005,
      9709, 50958, 64566,  7893, 35398, 26789, 21405, 45438,
     57392,   723, 14827, 56072, 20379, 44408, 38464, 29859,
     41851, 16792, 31392, 38979,  3280, 60979, 54539, 14312,
     30615, 38260, 44620, 19631, 55356, 15071,   487, 58116,
     13532, 54847, 60679,  4068, 39799, 31124, 17068, 41039,
     61697,  5090, 10458, 51769, 24234, 48201, 34673, 26002,
     45642, 20649, 27537, 35186,  7649, 65282, 50234,  9945],
    [    0, 65534, 58337,  7199, 56287,  9249, 14398, 51136,
     43939, 21597, 18498, 47036, 28796, 36738, 37789, 27747,
     19291, 46245, 43194, 22340, 36996, 28538, 29541, 35995,
     57592,  7942,   793, 64743, 15143, 50393, 55494, 10040,
     38582, 26952, 30039, 35497, 19817, 45719, 44680, 20854,
     15637, 49899, 57076,  8458, 59082,  6452,  1323, 64213,
     56813,  8723, 15884, 49650,  1586, 63948, 58835,  6701,
     30286, 35248, 38319, 27217, 44433, 21103, 20080, 45454,
     12657, 52879, 53904, 11630, 60078,  5456,  2383, 63153,
     39634, 25900, 31027, 34509, 16653, 48883, 41708, 23826,
     31274, 34260, 39371, 26165, 41461, 24075, 16916, 48618,
     53641, 11895, 12904, 52630,  2646, 62888, 59831,  5705,
     42951, 22585, 17446, 48088, 31768, 33766, 40953, 24583,
      3172, 62362, 61317,  4219, 55227, 10309, 13402, 52132,
     60572,  4962,  3965, 61571, 14147, 51389, 54434, 11100,
     18239, 47297, 42206, 23328, 40160, 25374, 32513, 33023,
     25314, 40220, 33027, 32509, 47421, 18115, 23260, 42274,
     51521, 14015, 10912, 54622,  4766, 60768, 61823,  3713,
     10681, 54855, 51800, 13734, 62054,  3480,  4487, 61049,
     33306, 32228, 25083, 40453, 22981, 42555, 47652, 17882,
     62548,  2986,  6069, 59467, 12171, 53365, 52330, 13204,
     24567, 40969, 48150, 17384, 33832, 31702, 26569, 38967,
     48911, 16625, 23790, 41744, 25808, 39726, 34609, 30927,
      5292, 60242, 63309,  2227, 53107, 12429, 11410, 54124,
     21395, 44141, 45170, 20364, 34892, 30642, 27565, 37971,
     63536,  1998,  7121, 58415,  9199, 56337, 49166, 16368,
      6344, 59190, 64297,  1239, 49943, 15593,  8438, 57096,
     45931, 19605, 20618, 44916, 26804, 38730, 35669, 29867,
     50469, 15067,  9924, 55610,  7930, 57604, 64795,   741,
     28294, 37240, 36199, 29337, 46425, 19111, 22200, 43334,
     36478, 29056, 28063, 37473, 21921, 43615, 46656, 18878,
      9693, 55843, 50748, 14786, 65026,   508,  7651, 57885],
    [    0, 32638, 65276, 33154, 57829, 40603,  7961, 24679,
     57303, 41129,  8491, 24149, 15922, 16716, 49358, 49072,
     41907, 56525, 23887,  8753, 16982, 15656, 48298, 50132,
     31844,   794, 33432, 64998, 40321, 58111, 25469,  7171,
     23419,  9221, 42375, 56057, 47774, 50656, 17506, 15132,
     33964, 64466, 31312,  1326, 25929,  6711, 39861, 58571,
     63688, 34742,  1588, 31050,  6445, 26195, 59345, 39087,
     10015, 22625, 55779, 42653, 50938, 47492, 14342, 18296,
     46838, 51592, 18442, 14196, 22291, 10349, 43503, 54929,
     26913,  5727, 38877, 59555, 35012, 63418, 30264,  2374,
      5445, 27195, 60345, 38087, 62624, 35806,  2652, 29986,
     51858, 46572, 13422, 19216, 11127, 21513, 54667, 43765,
     60813, 37619,  4977, 27663,  3176, 29462, 62100, 36330,
     12890, 19748, 52390, 46040, 54207, 44225, 11587, 21053,
     20030, 12608, 45250, 53180, 45019, 53413, 20775, 11865,
     37353, 61079, 28437,  4203, 28684,  3954, 36592, 61838,
     29169,  3727, 36621, 61555, 36884, 61290, 28392,  4502,
     44582, 53592, 20698, 12196, 20419, 12477, 45375, 52801,
     53826, 44348, 11454, 21440, 13223, 19673, 52571, 45605,
      3477, 29419, 62313, 35863, 60528, 37646,  4748, 28146,
     10890, 22004, 54390, 43784, 52079, 46097, 13715, 19181,
     62813, 35363,  2977, 29919,  5304, 27590, 59972, 38202,
     35129, 63047, 30661,  2235, 26844,  6050, 38432, 59742,
     22254, 10640, 43026, 55148, 46859, 51317, 18935, 13961,
     50951, 47225, 14843, 18053,  9954, 22940, 55326, 42848,
      6352, 26542, 58924, 39250, 63797, 34379,  1993, 30903,
     25780,  7114, 39496, 58678, 34129, 64047, 31661,  1235,
     47971, 50205, 17823, 15073, 23174,  9720, 42106, 56068,
     40060, 58114, 25216,  7678, 32153,   743, 33637, 64539,
     17323, 15573, 48471, 49705, 41550, 56624, 23730,  9164,
     16335, 16561, 49459, 48717, 56874, 41300,  8406, 24488,
     57368, 40806,  7908, 24986,   509, 32387, 65281, 32895],
    [    0, 16190, 32380, 16706, 64760, 50118, 33412, 48570,
     58861, 56019, 39825, 42159,  6421,  9771, 26473, 22615,
     55239, 59641, 43451, 38533, 11071,  5121, 21827, 27261,
     12842,  3348, 19542, 29544, 52946, 61932, 45230, 36752,
     45971, 36013, 52719, 62161, 20331, 28757, 12567,  3625,
     22142, 26944, 10242,  5948, 43654, 38328, 54522, 60356,
     25684, 23402,  6696,  9494, 39084, 42898, 59088, 55790,
     33209, 48775, 65477, 49403, 32065, 17023,   829, 15363,
     31547, 17413,  1351, 14969, 34755, 47357, 63935, 50817,
     40662, 41448, 57514, 57236, 25134, 23824,  7250,  9068,
     44284, 37826, 53888, 60862, 20484, 28474, 11896,  4422,
     18705, 30255, 14189,  2131, 46569, 35543, 52117, 62635,
     51368, 63382, 46804, 35306, 13392,  2926, 18988, 29970,
     11589,  4731, 21305, 27655, 53693, 61059, 44993, 37119,
      8047,  8273, 24851, 24109, 58263, 56489, 40427, 41685,
     64130, 50620, 34046, 48064,  1658, 14660, 30726, 18232,
     63094, 51528, 34826, 46900,  2702, 13744, 29938, 19404,
      5019, 11429, 28135, 21209, 61283, 53341, 37151, 44577,
      8625,  7823, 24525, 24819, 56649, 57975, 41781, 39947,
     50268, 64354, 47648, 34078, 14500,  1946, 18136, 31206,
     17893, 31451, 15257,  1191, 47389, 34339, 51041, 63583,
     40968, 40758, 56948, 57674, 23792, 25550,  8844,  7602,
     37410, 44316, 60510, 54112, 28378, 20964,  4262, 12184,
     30671, 18673,  2483, 13965, 35639, 46089, 62795, 51829,
     36173, 45683, 62257, 52239, 29109, 20107,  4041, 12535,
     26784, 22430,  5852, 10722, 37976, 43878, 59940, 54554,
     23178, 26036,  9462,  7112, 42610, 39244, 55310, 59184,
     48999, 32857, 49435, 65061, 17311, 31905, 15843,   733,
     16094,   480, 16546, 32668, 49702, 64792, 48218, 33636,
     56115, 58381, 42319, 39537, 10187,  6389, 22967, 26249,
     59673, 54823, 38757, 43099,  5601, 10975, 27549, 21667,
      3316, 13258, 29320, 19894, 61452, 53042, 36464, 45390],
    [    0,  7966, 15932,  8482, 31864, 25446, 16964, 23898,
     63728, 59374, 50892, 55762, 33928, 39830, 47796, 42410,
     60925, 62179, 54209, 52447, 37253, 36507, 44985, 45223,
      5389,  2579, 11057, 13359, 26997, 30315, 22345, 18519,
     51175, 55545, 63963, 59077, 48031, 42113, 34211, 39613,
     16151,  8201,   299,  7733, 17263, 23665, 32083, 25165,
     10778, 13572,  5158,  2872, 22114, 18812, 26718, 30528,
     53994, 52724, 60630, 62408, 44690, 45452, 37038, 36784,
     37843, 36045, 44527, 45809, 61355, 61621, 53655, 52873,
     27427, 29757, 21791, 18945,  5979,  2117, 10599, 13945,
     32302, 24880, 16402, 24332,   598,  7496, 15466,  9076,
     34526, 39360, 47330, 43004, 64166, 58808, 50330, 56196,
     21556, 19242, 27144, 29974, 10316, 14162,  5744,  2414,
     44228, 46042, 37624, 36326, 53436, 53154, 61056, 61854,
     47561, 42711, 34805, 39147, 50609, 55983, 64397, 58515,
     16697, 24103, 32517, 24603, 15681,  8799,   893,  7267,
     15291,  9381,  1415,  6809, 18371, 22749, 31231, 26337,
     49995, 56405, 64887, 57961, 48947, 41005, 33039, 40465,
     54854, 51544, 59514, 63332, 43582, 46368, 37890, 35612,
     11958, 12712,  4234,  3988, 21198, 19920, 27890, 29676,
     64604, 58178, 49760, 56702, 32804, 40762, 48664, 41222,
      1196,  7090, 14992,  9614, 30932, 26570, 18152, 23030,
      4513,  3775, 12189, 12419, 28121, 29383, 21477, 19707,
     59729, 63055, 55149, 51315, 38185, 35383, 43797, 46091,
     43112, 46966, 38484, 35146, 54288, 51982, 59948, 62770,
     20632, 20358, 28324, 29114, 11488, 13310,  4828,  3522,
     17813, 23179, 31657, 25783, 14829,  9971,  2001,  6351,
     48485, 41595, 33625, 40007, 49437, 56835, 65313, 57407,
     28559, 28817, 20915, 20141,  5111,  3305, 11723, 13013,
     38783, 34913, 43331, 46685, 60167, 62489, 54587, 51749,
     33394, 40300, 48206, 41808, 65034, 57620, 49206, 57128,
     31362, 26012, 17598, 23456,  1786,  6628, 14534, 10200],
    [    0,  3854,  7708,  4370, 15416, 13110,  8740, 11562,
     30832, 30590, 26220, 26978, 17480, 19270, 23124, 21850,
     61664, 65518, 61180, 57842, 52440, 50134, 53956, 56778,
     34960, 34718, 38540, 39298, 46248, 48038, 43700, 42426,
     64989, 62163, 58305, 60623, 49637, 52971, 57337, 53495,
     34221, 35491, 39857, 38079, 47509, 46747, 42889, 43143,
      3389,   563,  4897,  7215, 12549, 15883, 12057,  8215,
     30029, 31299, 27473, 25695, 18805, 18043, 22377, 22631,
     59303, 59561, 63931, 63157, 56223, 54417, 50563, 51853,
     40919, 37081, 33227, 36549, 41967, 44257, 48627, 45821,
      5959,  6217,  2395,  1621, 11135,  9329, 13667, 14957,
     28471, 24633, 28971, 32293, 21263, 23553, 19731, 16925,
      6778,  5492,  1126,  2920,  9794, 10572, 14430, 14160,
     25098, 27908, 31766, 29464, 24114, 20796, 16430, 20256,
     60058, 58772, 62598, 64392, 54946, 55724, 51390, 51120,
     37610, 40420, 36086, 33784, 44754, 41436, 45262, 49088,
     54099, 56413, 52559, 49729, 61291, 57445, 61815, 65145,
     43811, 42029, 46399, 47665, 38683, 38933, 35079, 34313,
      9139, 11453, 15791, 12961,  8075,  4229,   407,  3737,
     23491, 21709, 17887, 19153, 26619, 26869, 31207, 30441,
     11918,  8576, 12434, 16284,  4790,  7608,  3242,   932,
     22270, 23024, 18658, 18412, 27334, 26056, 29914, 31700,
     56942, 53600, 49266, 53116, 57942, 60760, 64586, 62276,
     42526, 43280, 47106, 46860, 39462, 38184, 33850, 35636,
     13556, 15354, 10984,  9702,  2252,  1986,  5840,  6622,
     19588, 17290, 21144, 23958, 28860, 32690, 28320, 25006,
     50196, 51994, 55816, 54534, 63532, 63266, 58928, 59710,
     48228, 45930, 41592, 44406, 32860, 36690, 40512, 37198,
     51497, 50727, 55093, 55355, 62737, 64031, 60173, 58371,
     45401, 48727, 44869, 41035, 36193, 33391, 37757, 40051,
     14793, 14023, 10197, 10459,  1521,  2815,  7149,  5347,
     16825, 20151, 24485, 20651, 32129, 29327, 25501, 27795],
    [    0,  1798,  3596,  2314,  7192,  6942,  4628,  5394,
     14384, 16182, 13884, 12602,  9256,  9006, 10788, 11554,
     28768, 30566, 32364, 31082, 27768, 27518, 25204, 25970,
     18512, 20310, 18012, 16730, 21576, 21326, 23108, 23874,
     57536, 59334, 61132, 59850, 64728, 64478, 62164, 62930,
     55536, 57334, 55036, 53754, 50408, 50158, 51940, 52706,
     37024, 38822, 40620, 39338, 36024, 35774, 33460, 34226,
     43152, 44950, 42652, 41370, 46216, 45966, 47748, 48514,
     56733, 55963, 54161, 54423, 49541, 50819, 53129, 51343,
     58797, 58027, 60321, 60583, 63925, 65203, 63417, 61631,
     44541, 43771, 41969, 42231, 45541, 46819, 49129, 47343,
     38349, 37579, 39873, 40135, 35285, 36563, 34777, 32991,
     15709, 14939, 13137, 13399,  8517,  9795, 12105, 10319,
      1389,   619,  2913,  3175,  6517,  7795,  6009,  4223,
     19773, 19003, 17201, 17463, 20773, 22051, 24361, 22575,
     29965, 29195, 31489, 31751, 26901, 28179, 26393, 24607,
     42791, 40993, 43307, 44589, 47935, 48185, 46387, 45621,
     40727, 38929, 37147, 38429, 33551, 33801, 36099, 35333,
     55111, 53313, 55627, 56909, 52063, 52313, 50515, 49749,
     61303, 59505, 57723, 59005, 62319, 62569, 64867, 64101,
     18407, 16609, 18923, 20205, 23551, 23801, 22003, 21237,
     32727, 30929, 29147, 30429, 25551, 25801, 28099, 27333,
     14215, 12417, 14731, 16013, 11167, 11417,  9619,  8853,
      4023,  2225,   443,  1725,  5039,  5289,  7587,  6821,
     31418, 32188, 29878, 29616, 26274, 24996, 26798, 28584,
     17034, 17804, 19590, 19328, 24210, 22932, 20638, 22424,
      2778,  3548,  1238,   976,  5826,  4548,  6350,  8136,
     13034, 13804, 15590, 15328, 12018, 10740,  8446, 10232,
     39546, 40316, 38006, 37744, 34402, 33124, 34926, 36712,
     41546, 42316, 44102, 43840, 48722, 47444, 45150, 46936,
     59930, 60700, 58390, 58128, 62978, 61700, 63502, 65288,
     53802, 54572, 56358, 56096, 52786, 51508, 49214, 51000],
    [    0,   770,  1540,  1286,  3080,  3850,  2572,  2318,
      6160,  6930,  7700,  7446,  5144,  5914,  4636,  4382,
     12320, 13090, 13860, 13606, 15400, 16170, 14892, 14638,
     10288, 11058, 11828, 11574,  9272, 10042,  8764,  8510,
     24640, 25410, 26180, 25926, 27720, 28490, 27212, 26958,
     30800, 31570, 32340, 32086, 29784, 30554, 29276, 29022,
     20576, 21346, 22116, 21862, 23656, 24426, 23148, 22894,
     18544, 19314, 20084, 19830, 17528, 18298, 17020, 16766,
     49280, 50050, 50820, 50566, 52360, 53130, 51852, 51598,
     55440, 56210, 56980, 56726, 54424, 55194, 53916, 53662,
     61600, 62370, 63140, 62886, 64680, 65450, 64172, 63918,
     59568, 60338, 61108, 60854, 58552, 59322, 58044, 57790,
     41152, 41922, 42692, 42438, 44232, 45002, 43724, 43470,
     47312, 48082, 48852, 48598, 46296, 47066, 45788, 45534,
     37088, 37858, 38628, 38374, 40168, 40938, 39660, 39406,
     35056, 35826, 36596, 36342, 34040, 34810, 33532, 33278,
     40221, 40479, 39705, 38939, 37141, 37399, 38673, 37907,
     34061, 34319, 33545, 32779, 35077, 35335, 36609, 35843,
     44349, 44607, 43833, 43067, 41269, 41527, 42801, 42035,
     46381, 46639, 45865, 45099, 47397, 47655, 48929, 48163,
     64861, 65119, 64345, 63579, 61781, 62039, 63313, 62547,
     58701, 58959, 58185, 57419, 59717, 59975, 61249, 60483,
     52605, 52863, 52089, 51323, 49525, 49783, 51057, 50291,
     54637, 54895, 54121, 53355, 55653, 55911, 57185, 56419,
     23965, 24223, 23449, 22683, 20885, 21143, 22417, 21651,
     17805, 18063, 17289, 16523, 18821, 19079, 20353, 19587,
     28093, 28351, 27577, 26811, 25013, 25271, 26545, 25779,
     30125, 30383, 29609, 28843, 31141, 31399, 32673, 31907,
     15837, 16095, 15321, 14555, 12757, 13015, 14289, 13523,
      9677,  9935,  9161,  8395, 10693, 10951, 12225, 11459,
      3581,  3839,  3065,  2299,   501,   759,  2033,  1267,
      5613,  5871,  5097,  4331,  6629,  6887,  8161,  7395],
]

def crc32(data: bytes):
    result = 0
    for value in data:
        result = EDC_crctable[(result ^ value) & 0xFF] ^ (result >> 8)
    return result


L2_RAW = 0x800
L2_P = 43*2*2
L2_Q = 26*2*2
def encode_L2_P(data: bytes) -> bytes:
    base_index = 0
    P_index = 4 + L2_RAW + 4 + 8
    target_size = P_index + L2_P
    data = list(data) + ([None] * (target_size-len(data)))
    assert len(data) == target_size
    for j in range(43):
        a, b = 0, 0
        index = base_index
        for i in range(19, 43):
            assert index < P_index-1
            a ^= L2sq[i][data[index]]
            b ^= L2sq[i][data[index+1]]
            index += (2*43)

        data[P_index] = a >> 8
        data[P_index + (43*2)] = a & 0xFF
        data[P_index + 1] = b >> 8
        data[P_index + (43*2) + 1] = b & 0xFF
        base_index += 2
        P_index += 2
    assert None not in data
    return data

def encode_L2_Q(data: bytes) -> bytes:
    base_index = 0
    Q_index = 4 + L2_RAW + 4 + 8 + L2_P
    MOD_INDEX = Q_index
    target_size = Q_index + L2_Q
    data = data + ([None] * (target_size-len(data)))
    assert len(data) == target_size
    counter = 0
    for _ in range(26):
        a, b = 0, 0
        index = base_index
        for i in range(43):
            a ^= L2sq[i][data[index]]
            b ^= L2sq[i][data[index+1]]
            index += (2*44)
            index = index % MOD_INDEX
        data[Q_index] = a >> 8
        data[Q_index + (26*2)] = a & 0xFF
        data[Q_index + 1] = b >> 8
        data[Q_index + (26*2) + 1] = b & 0xFF
        base_index += (2*43)
        Q_index += 2
        counter += 1
    assert None not in data
    return data

def get_edc_ecc(data: bytes):
    assert len(data) == 0x818
    edc = crc32(data[0x10:0x818])
    for _ in range(4):
        data += bytes([edc & 0xFF])
        edc >>= 8
    assert len(data) == 0x81c
    assert len(data)-12 == 0x810
    temp = encode_L2_P(bytes([0, 0, 0, 0]) + data[0x10:])
    temp = encode_L2_Q(temp)
    data += bytes(temp[-0x114:])
    assert len(data) == 0x930
    return data[0x818:0x81c], data[0x81c:]

DELTA_FILE = environ.get('DELTA')

def write_data_to_sectors(imgname, initial_sector, datafile=None, force_recalc=False):
    if datafile is None:
        datafile = path.join(SANDBOX_PATH, "_temp.bin")

    f = open(imgname, "r+b")
    g = open(datafile, "r+b")
    filesize = stat(datafile).st_size

    delta = None
    if DELTA_FILE is not None:
        delta = open(DELTA_FILE, "a+")
    if not hasattr(write_data_to_sectors, "_done_delta"):
        write_data_to_sectors._done_delta = set()

    sector_index = initial_sector
    while True:
        pointer = sector_index * 0x930
        f.seek(pointer)
        block = g.read(0x800)
        if len(block) < 0x800:
            block += bytes(0x800 - len(block))
        assert len(block) == 0x800

        if g.tell() >= filesize:
            assert g.tell() == filesize
            eof = 0x80
            eor = 0x01
        else:
            eof = 0
            eor = 0
        rt = 0
        form = 0
        trigger = 0
        data = 0x08
        audio = 0
        video = 0
        submode = eof | rt | form | trigger | data | audio | video | eor
        f.seek(pointer + 0x12)
        old_submode = ord(f.read(1))
        if args.debug and submode & 0x7E != old_submode & 0x7E:
            print(
                "WARNING! Submode differs on sector %s: %x -> %x"
                % (sector_index, old_submode, submode)
            )

        f.seek(pointer + 0x18)
        old_block = f.read(0x800)
        if force_recalc or old_block != block:
            if args.debug:
                print("Writing: {0} {1:0>8x}".format(datafile, pointer))
            f.seek(pointer + 0x12)
            f.write(bytes([submode]))
            f.seek(pointer + 0x16)
            f.write(bytes([submode]))
            f.seek(pointer + 0x18)
            f.write(block)
            f.seek(pointer)
            sector_data = f.read(0x818)
            edc, ecc = get_edc_ecc(sector_data)
            assert len(edc + ecc) == 0x118
            f.seek(pointer + 0x818)
            f.write(edc + ecc)
            if delta is not None and (
                (pointer, pointer + 0x930) not in write_data_to_sectors._done_delta
            ):
                write_data_to_sectors._done_delta.add((pointer, pointer + 0x930))
                delta.write("{0:0>8x} {1:0>8x}\n".format(pointer, pointer + 0x930))

        if eof and eor:
            break
        sector_index += 1

    f.close()
    g.close()

    if delta is not None:
        delta.close()


class FileManager(object):
    SKIP_REALIGNMENT: bool

    def __init__(
        self,
        imgname: str,
        dirname: str | None = None,
        minute: int = 0,
        second: int = 2,
        sector: int = 22,
    ):
        if dirname is None:
            dirname, _ = imgname.rsplit(".", 1)
            dirname = "%s.root" % dirname
        self.imgname = imgname
        self.dirname = dirname
        self.minute = minute
        self.second = second
        self.sector = sector
        self.files = read_directory(
            imgname, dirname, minute=minute, second=second, sector=sector
        )

    @property
    def flat_files(self) -> list[FileEntry]:
        if hasattr(self, "_flat_files"):
            return self._flat_files

        files = list(self.files)
        while True:
            for f in list(files):
                if f.is_directory:
                    files.remove(f)
                    new_files = f.files
                    if new_files is not None:
                        files.extend(new_files)
                    break
            else:
                break

        self._flat_files = files
        return self.flat_files

    @property
    def flat_directories(self):
        files = list(self.files)
        directories = []
        while files:
            f = files.pop(0)
            if f.is_directory:
                new_files = f.files
                directories.append(f)
                if new_files is not None:
                    files.extend(new_files)
        return directories

    @property
    def report(self):
        s = ""
        for f in sorted(
            self.flat_files, key=lambda f2: (f2.initial_sector, f2.pointer)
        ):
            assert str(f).startswith(self.dirname)
            filepath = str(f)[len(self.dirname) :]
            if filepath.endswith(";1"):
                filepath = filepath[:-2]
            s += "{0:0>8x} {1:0>4x} {2:0>7x} {3}\n".format(
                f.target_sector * 0x930, f.pointer, f.size, filepath
            )
        return s.strip()

    def write_all(self):
        for f in self.flat_files:
            f.write_data()

    def get_file(self, name: str) -> FileEntry:
        if not hasattr(self, "_name_cache"):
            self._name_cache: dict[str, FileEntry] = {}

        if not name.endswith(";1"):
            name = name + ";1"

        if name.startswith(SANDBOX_PATH):
            name = name[len(SANDBOX_PATH) :].lstrip(path.sep)

        if name in self._name_cache:
            return self._name_cache[name]

        filepath = path.join(self.dirname, name)
        for f in self.flat_files:
            if f.path == filepath:
                self._name_cache[name] = f
                return self.get_file(name)
        raise ValueError("File not found: %s" % name)

    def export_file(self, name, filepath=None):
        if not name.endswith(";1"):
            name = name + ";1"
        if filepath is None:
            filepath = path.join(self.dirname, name)
        dirname = path.split(filepath)[0]
        if dirname and not path.exists(dirname):
            makedirs(dirname)
        f = self.get_file(name)
        if f is None:
            return None
        f.write_data(filepath)
        return filepath

    def calculate_free(self):
        max_size = stat(self.imgname).st_size
        max_sectors = max_size // 0x930

        used_sectors = set()
        for f in self.flat_files:
            num_sectors = ceil(f.num_sectors)
            num_sectors = max(num_sectors, 1)
            used_sectors |= set(range(f.target_sector, f.target_sector + num_sectors))

        last_sector = max_size // 0x930
        unused_sectors = set(range(max_sectors)) - used_sectors

        final_unused_sectors = []
        with open(self.imgname, "rb") as f:
            previous_unused = -999
            for sector in sorted(unused_sectors):
                pointer = (sector * 0x930) + 0x18
                f.seek(pointer)
                block = f.read(0x800)
                if set(block) in ({0}, {0xFF}):
                    if sector == previous_unused + 1:
                        final_unused_sectors[-1].append(sector)
                    else:
                        final_unused_sectors.append([sector])
                    previous_unused = sector

        self._free_sectors = final_unused_sectors

    def get_free(self, num_sectors):
        if not hasattr(self, "_free_sectors"):
            self.calculate_free()

        candidates = [
            sectors
            for sectors in sorted(self._free_sectors, key=lambda s: (len(s), s[0]))
            if len(sectors) >= num_sectors
        ]
        chosen = candidates[0]
        self._free_sectors.remove(chosen)
        new_target_sector = chosen[0]
        used, unused = chosen[:num_sectors], chosen[num_sectors:]
        assert len(used) == num_sectors
        if unused:
            self._free_sectors.append(unused)

        return new_target_sector

    def realign_entry_pointers(self):
        if hasattr(self, "SKIP_REALIGNMENT") and self.SKIP_REALIGNMENT:
            return

        all_files = self.flat_directories + self.flat_files
        initial_sectors = {f.initial_sector for f in all_files}
        for initial_sector in sorted(initial_sectors):
            files = [f for f in all_files if f.initial_sector == initial_sector]
            files = sorted(
                files, key=lambda f: f.pointer if f.pointer is not None else 0xFFFFFFFF
            )
            pointer = 0
            highest_old_pointer = 0
            highest_pointer = 0
            for f in files:
                old_sector = pointer // 0x800
                new_sector = (pointer + f.size) // 0x800
                if new_sector == old_sector + 1:
                    pointer = new_sector * 0x800
                else:
                    assert new_sector == old_sector

                if f.pointer is not None:
                    highest_old_pointer = max(highest_old_pointer, f.pointer)

                f.pointer = pointer
                highest_pointer = max(highest_pointer, f.pointer)
                pointer += f.size
                f.update_file_entry()

            assert highest_old_pointer // 0x800 == highest_pointer // 0x800

    def create_new_file(self, name: str, template: FileEntry | None):
        template.initial_sector
        template.target_sector
        new_file = FileEntry(
            template.imgname, None, template.dirname, template.initial_sector
        )
        new_file.clone_entry(template)
        head, tail = path.split(name)
        new_file.name = tail
        new_file._size = new_file.size
        self._flat_files.append(new_file)
        self.realign_entry_pointers()
        return new_file

    def import_file(
        self,
        name: str,
        filepath=None,
        new_target_sector=None,
        force_recalc=False,
        verify=False,
        template=None,
    ):
        if not name.endswith(";1"):
            name = name + ";1"
        if filepath is None:
            filepath = path.join(self.dirname, name)
        if filepath.endswith(";1"):
            filepath = filepath[:-2]

        new_size = ceil(stat(filepath).st_size / 0x800)
        new_size = max(new_size, 1)
        old_file = self.get_file(name)

        if old_file is not None:
            to_import = old_file
            if new_target_sector is None:
                old_size = ceil(old_file.filesize / 0x800)
                if new_size <= old_size:
                    new_target_sector = old_file.target_sector
            else:
                verify = True
        else:
            assert template
            to_import = self.create_new_file(name, template=template)

        if new_target_sector is None:
            new_target_sector = self.get_free(new_size)
            verify = True
            force_recalc = True

        assert new_target_sector is not None
        verify = verify or args.debug

        if verify:
            end_sector = new_target_sector + new_size

            self_path = path.join(self.dirname, name)
            for f in self.flat_files:
                if f.path == self_path:
                    continue
                try:
                    if f.start_sector <= new_target_sector:
                        assert f.end_sector <= new_target_sector
                    if f.start_sector >= new_target_sector:
                        assert end_sector <= f.start_sector
                except AssertionError:
                    raise Exception("Conflict with %s" % f)

        to_import.target_sector = new_target_sector
        to_import.filesize = new_size * 0x800
        if to_import.pointer is None:
            assert hasattr(self, "SKIP_REALIGNMENT")
            assert self.SKIP_REALIGNMENT
        else:
            to_import.update_file_entry()
        write_data_to_sectors(
            to_import.imgname,
            to_import.target_sector,
            datafile=filepath,
            force_recalc=force_recalc,
        )

        return to_import

    def finish(self):
        FileEntry.write_cached_files()


def patch_game_script(patch_script_text: str, warn_double_import: bool = True):
    to_import: dict[str, str] = {}
    identifier: str = MISSING
    script_text: str = MISSING

    # patch, validator = PatchParser()(patch_script_text)

    for line in patch_script_text.split("\n"):
        if "#" in line:
            index = line.index("#")
            line = line[:index].rstrip()
        line = line.lstrip()
        if not line:
            continue
        if line.startswith("!"):
            line = line.strip().lower()
            while "  " in line:
                line = line.replace("  ", " ")
            if line.startswith("!npc"):
                (_command, npc_index, misc, location) = line.split()
                map_index, location = location.split(":")
                a, b = location.split(",")
                map_index = int(map_index, 0x10)
                if npc_index == "+1":
                    npc_index = None
                else:
                    npc_index = int(npc_index, 0x10)
                try:
                    assert misc.startswith("(")
                    assert misc.endswith(")")
                except Exception as e:
                    raise Exception('Malformed "misc" field: %s' % line) from e
                misc = int(misc[1:-1], 0x10)
                (x, y, boundary_west, boundary_east, boundary_north, boundary_south) = (
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                )
                for axis, value_range in zip(("x", "y"), (a, b)):
                    try:
                        assert ">" not in value_range
                        if "<" in value_range:
                            left, middle, right = value_range.split("<=")
                            left = int(left, 0x10)
                            middle = int(middle, 0x10)
                            right = int(right, 0x10)
                            assert left <= middle <= right
                            if axis == "x":
                                boundary_west = left
                                x = middle
                                boundary_east = right
                            else:
                                assert axis == "y"
                                boundary_north = left
                                y = middle
                                boundary_south = right
                        else:
                            if axis == "x":
                                x = int(value_range, 0x10)
                            else:
                                assert axis == "y"
                                y = int(value_range, 0x10)
                    except Exception as e:
                        raise Exception("Malformed coordinates: %s" % line) from e
                boundary = (
                    (boundary_west, boundary_north),
                    (boundary_east, boundary_south),
                )
                MapMetaObject.get(map_index).set_npc(
                    x, y, boundary, misc, npc_index
                )
            elif line.startswith("!exit"):
                try:
                    (_command, exit_index, misc, movement, dimensions) = line.split()
                except ValueError:
                    (_command, exit_index, misc, movement) = line.split()
                    dimensions = "1x1"
                if exit_index == "+1":
                    exit_index = None
                else:
                    exit_index = int(exit_index, 0x10)
                try:
                    assert misc.startswith("(")
                    assert misc.endswith(")")
                except AssertionError as e:
                    raise Exception('Malformed "misc" field: %s' % line) from e
                misc = int(misc[1:-1], 0x10)

                source, destination = movement.split("->")
                source_index, source_location = source.split(":")
                dest_index, dest_location = destination.split(":")
                boundary_west, boundary_north = source_location.split(",")
                dest_x, dest_y = dest_location.split(",")
                width, height = dimensions.split("x")

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
                boundary = (
                    (boundary_west, boundary_north),
                    (boundary_east, boundary_south),
                )
                MapMetaObject.get(source_index).add_or_replace_exit(
                    boundary, dest_index, dest_x, dest_y, misc, exit_index
                )
            elif line.startswith("!tile"):
                try:
                    (_command, tile_index, location, dimensions) = line.split()
                except ValueError:
                    (_command, tile_index, location) = line.split()
                    dimensions = "1x1"
                map_index, location = location.split(":")
                boundary_west, boundary_north = location.split(",")
                width, height = dimensions.split("x")
                assert tile_index != "+1"
                tile_index = int(tile_index, 0x10)
                map_index = int(map_index, 0x10)
                boundary_west = int(boundary_west, 0x10)
                boundary_north = int(boundary_north, 0x10)
                width = int(width)
                height = int(height)
                boundary_east = boundary_west + width
                boundary_south = boundary_north + height
                boundary = (
                    (boundary_west, boundary_north),
                    (boundary_east, boundary_south),
                )
                MapMetaObject.get(map_index).add_or_replace_tile(boundary, tile_index)
            else:
                raise Exception("Unknown event patch command: %s" % line)
            continue

        if line.startswith("EVENT"):
            while "  " in line:
                line = line.replace("  ", " ")
            if identifier is not MISSING:
                assert identifier not in to_import
                to_import[identifier] = script_text
            identifier = line.strip().split(" ")[-1]
            script_text = ""
        else:
            script_text = "\n".join([script_text, line])  # type: ignore


    assert identifier not in to_import
    to_import[identifier] = script_text
    for identifier, script_text in sorted(to_import.items()):
        map_index, el_index, script_index = identifier.split("-")
        map_index = int(map_index, 0x10)
        script_index = None if script_index == "XX" else int(script_index, 0x10)
        meo = MapEventObject.get(map_index)
        el = meo.get_eventlist_by_index(el_index)
        script = el.get_or_create_script_by_index(script_index)
        script.import_script(script_text, warn_double_import=warn_double_import)


EVENT_PATCHES = [
    "skip_tutorial",
    "treadool_warp",
]


def patch_events(filenames: list[str] | None = None, warn_double_import: bool = True):
    if filenames is None:
        filenames = []
        for label in EVENT_PATCHES:
            filenames.append(label)
            filename = path.join(tblpath, "eventpatch_{0}.txt".format(label))

    if not filenames:
        return

    if not isinstance(filenames, list):
        filenames = [filenames]

    filenames = [
        fn
        if fn.endswith(".txt")
        else path.join(tblpath, "eventpatch_{0}.txt".format(fn))
        for fn in filenames
    ]

    patch_script_text = ""
    for filename in filenames:
        for line in read_lines_nocomment(filename):
            patch_script_text += line + "\n"
    patch_script_text = patch_script_text.strip()
    patch_game_script(patch_script_text, warn_double_import=warn_double_import)
