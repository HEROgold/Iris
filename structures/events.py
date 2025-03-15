from __future__ import annotations

import logging
from string import ascii_letters, digits, punctuation
from _types.objects import Cache
from constants import POINTER_SIZE
from enums.event_scripts import EventClass
from helpers.files import read_file, restore_pointer
from typing import TYPE_CHECKING, Self, TypedDict
from abc_.pointers import TablePointer
from helpers.bits import read_little_int
from helpers.name import read_as_decompressed_name
from structures.word import Word
from tables import MapEventObject
from logger import iris
from tables import EventInstObject

if TYPE_CHECKING:
    from structures.zone import Zone


# TODO: find out what this is used for.
class Event(TablePointer):
    _event_script: EventScript | None
    zone: Zone
    event_class: EventClass
    event_index: int

    def __init__(self, address: int, index: int) -> None:
        super().__init__(address, index)

    @classmethod
    def from_index(cls, index: int) -> Self:
        return cls.from_table(EventInstObject.address, index)

    @classmethod
    def from_table(cls, address: int, index: int) -> Self:
        from structures.zone import Zone
        inst = cls(address, index)
        inst.pointer
        read_file.seek(inst.pointer)
        inst.zone = Zone.from_index(read_little_int(read_file, 1))
        inst.event_class = EventClass(read_little_int(read_file, 1))
        inst.event_index = read_little_int(read_file, 1)
        # inst._event_script = EventScript(pointer, 0)
        # inst._event_script.read() # TESTING TEMP
        return inst

    def write(self):
        return

    def parse_text(self):
        # TODO: Read from Terrorwave and parse using read_file reader.
        pass

    def parse_event(self):
        # TODO: Read from Terrorwave and parse using read_file reader.
        pass

    def parse_variables(self):
        # TODO: Read from Terrorwave and parse using read_file reader.
        pass

    def parse_pointers(self, count: int, pointers: bytes):
        # TODO: transform to read_file reader.
        res: list[int] = []
        for i in range(count - 1):
            res.append(int.from_bytes(pointers[i:i+POINTER_SIZE]))
        return res


MAP_EVENT_SIZE = sum(
    [
        MapEventObject.eventlist_lowbytes,
        MapEventObject.eventlist_highbyte,
        MapEventObject.npc_lowbytes,
        MapEventObject.npc_highbyte,
        MapEventObject.map_name_pointer,
    ]
)

"""
Event Identifiers

Now let's talk about some technical details that may not be readily apparent.
First, every event script in the dump has a unique identifier.
The identifier for our "Hello World!" event was 04-B-01.
There are three parts of this identifier.
The first part of the identifier specifies Map 04, which is the interior of buildings in Elcid.
The second part indicates that this is a class B event, which I will explain in detail below.
The final part is the event index, indicating that this is the 01th B event.


You'll notice that there are five different classes of events: A, B, C, D, and X.
I'll give you a brief description of each event class.


X: This script runs on map loading and is mainly used to load NPC sprites, BGM, and set map properties.
This is a special class of script, and many instructions will not work if you put them here.
However, using event flags for branching conditions seems to work fine.
Note that there is also much more limited space for these events,
because they are stored separately from the normal event classes,
so deleting an ABCD event will not free up any space for X events.


A: This script also runs on map load, but you can use any instructions you want and they share space with BCD events.
However, you can only have two A events per map: A-00 and A-01. Any A event with a higher index will be ignored.


B: This class of script is exclusively called from other events;
for example, when a cutscene needs to make a scene transition to a different map,
it will use the "Warp to Map & Event" instruction (opcode 16) to call a B class event.


C: These scripts are activated when you interact with NPCs.
Every townsperson dialogue in the game is a C class script.
However, to link the script to the appropriate NPC, you need to give the script a specific index.
NPC 01 calls the event script C-50, NPC 02 calls C-51, and so on.
In other words, the script index is equal to the NPC index plus 0x4F.
Additionally, there are special NPCs known as "roaming" NPCs that use indexes below 0x50.
For example, NPC 12 (Iris) will use the script C-12.


D: The last class of event scripts are activated when stepping on a particular tile.
These, too, must have the appropriate index that matches their associated tile.
For example, Tile 01 will call script D-01.

"""

class MapEvent(TablePointer):
    zone: Zone | None
    _cache = Cache[int, Self]()

    def __init__(
        self,
        pointer: int,
        eventlist_lowbytes: bytes,
        eventlist_highbyte: bytes,
        npc_lowbytes: bytes,
        npc_highbyte: bytes,
        map_name_pointer: int,
    ) -> None:
        self.logger = logging.getLogger(f"{iris.name}.{__class__.__name__}")
        self.pointer = pointer
        self._eventlist_lowbytes = eventlist_lowbytes
        self._eventlist_highbyte = eventlist_highbyte
        self._npc_lowbytes = npc_lowbytes
        self._npc_highbyte = npc_highbyte
        self._map_name_offset = map_name_pointer # FIXME: pointer at 169?
        self._event_lists: list[EventList] = []

    @classmethod
    def from_index(cls, index: int) -> Self:
        return cls.from_table(MapEventObject.address, index)

    @classmethod
    def from_table(cls, address: int, index: int) -> Self:
        if inst := cls._cache.from_cache(index):
            return inst

        pointer = address + index * MAP_EVENT_SIZE
        read_file.seek(pointer)
        inst = cls(
            pointer,
            read_file.read(MapEventObject.eventlist_lowbytes),
            read_file.read(MapEventObject.eventlist_highbyte),
            read_file.read(MapEventObject.npc_lowbytes),
            read_file.read(MapEventObject.npc_highbyte),
            read_little_int(read_file, MapEventObject.map_name_pointer),
        )
        inst.address = address
        inst.index = index
        inst._gen_scripts()

        cls._cache.to_cache(index, inst)
        return inst

    def _gen_scripts(self) -> None:
        read_file.seek(self.event_list_pointer)
        identifier = read_file.read(2)
        assert identifier == b"PH"

        self._npc_script = EventScript(self.base_pointer, self.npc_offset)

        for _ in range(6):
            offset = int.from_bytes(read_file.read(2), byteorder='little')
            event_list = EventList(self.event_list_pointer, offset)
            self._event_lists.append(event_list)

        self._npc_script.read()
        for event in self._event_lists:
            event.read()


    @property
    def map_name_pointer(self) -> int:
        return self.base_pointer + self._map_name_offset
    @property
    def map_name(self) -> bytes:
        return read_as_decompressed_name(self.map_name_pointer)

    @property
    def clean_map_name(self) -> bytes:
        return (
            self.map_name
            .replace(b"\x0A", b"")
            .replace(b"\x00", b"")
        )

    @property
    def base_pointer(self):
        assert self.pointer & 0xff8000 == 0x38000
        return self.pointer & 0xff8000

    @property
    def event_list_pointer(self) -> int:
        pointer = int.from_bytes(self._eventlist_lowbytes, "little") | (int.from_bytes(self._eventlist_highbyte) << 15)
        return self.base_pointer + pointer

    @event_list_pointer.setter
    def event_list_pointer(self, pointer: int) -> None:
        temp = pointer - self.base_pointer
        self.eventlist_highbyte = temp >> 15
        self.eventlist_lowbytes = temp & 0x7fff
        assert self.event_list_pointer == pointer

    @property
    def npc_offset(self) -> int:
        return int.from_bytes(self._npc_lowbytes, "little") | (int.from_bytes(self._npc_highbyte) << 15)

    @property
    def npc_pointer(self) -> int:
        return self.base_pointer + self.npc_offset

    @npc_pointer.setter
    def npc_pointer(self, pointer: int) -> None:
        temp = pointer - self.base_pointer
        self._npc_highbyte = (temp >> 15).to_bytes(1)
        self._npc_lowbytes = (temp & 0x7fff).to_bytes(1)
        assert self.npc_pointer == pointer

    def write(self):
        return


class EventList:
    # TODO: add caching?
    def __init__(self, pointer: int, offset: int) -> None:
        self.pointer = pointer
        self.offset = offset
        self._events: list[EventScript] = []
        self._gen_scripts() # Terrorwave only points to self.pointer for NPC scripts.

    @restore_pointer
    def _gen_scripts(self) -> None:
        read_file.seek(self.pointer + self.offset)
        while True:
            index = read_little_int(read_file, 1)
            # Do we need to keep track of these indices?

            if index == 0xFF:
                break

            offset = read_little_int(read_file, 2)
            script = EventScript(self.pointer, offset)
            self._events.append(script)


    def read(self):
        for event in self._events:
            event.read()



class OpCode(TypedDict):
    params: int
    comment: str



# Refer to L2_ScriptEvents.txt for more information.
op_codes: dict[int, OpCode] = {
    0x00: {"params": 0, "comment": "=> END"},
    0x01: {"params": 2, "comment": "=> IN TEXT MODE:  End of quote"}, # old > params: 0
    0x02: {"params": 2, "comment": "=> BRK"}, # old > params: 0
    0x03: {"params": 2, "comment": "=> IN TEXT MODE:  line break"}, # old > params: 0
    0x04: {"params": 2, "comment": "XX => IN TEXT MODE:  Pause ([P XX])"}, # old > params: 1
    0x05: {"params": 2, "comment": "XX => IN TEXT MODE:  05-shift"}, # old > params: 1 # old > params: 2
    0x06: {"params": 2, "comment": "XX => IN TEXT MODE:  06-shift"}, # old > params: 1
    0x07: {"params": 1, "comment": "XX => ???"},
    0x08: {"params": 0, "comment": "=> The character you're talking to speaks."}, # TODO: Handle this.
    0x09: {"params": 0, "comment": "=> IN TEXT MODE:  Hero's name (Maxim, if you didn't change it)"},
    0x0A: {"params": 2, "comment": "XX YY => 0A-pointer (relative)"},
    0x0B: {"params": 0, "comment": "=> IN TEXT MODE:  Selection Cursor (replaces 0x01 as EOQ byte). See 0x10"},
    0x0C: {"params": 0, "comment": "=> IN TEXT MODE:  ? + line break"},
    0x0D: {"params": 0, "comment": "=> IN TEXT MODE:   + line break"},
    0x0E: {"params": 0, "comment": "=> IN TEXT MODE:  , + line break"},
    0x0F: {"params": 0, "comment": "=> IN TEXT MODE:  . + line break"},
    0x10: {"params": 1, "comment": "XX (P1 P1, ...) => XX Choice, 2-byte pointers to replies."}, # TODO: handle this
    0x11: {"params": 0, "comment": "=> BRK"}, # No params? or 1 param?
    0x12: {"params": 2, "comment": "XX YY (P1 P1, ...) => ??? YY = the number of pointers"},
    0x13: {"params": 1, "comment": "XX => Character XX speaks spontaneously"},
    0x14: {"params": 1, "comment": """XX ... ? => ??? (0x14 FF => 2-bytes long instruction)"""}, # If flag is set, don't jump to offset.
    0x15: {"params": 3, "comment":"""XX YY ZZ => If the event flag number XX is set  => JUMP TO [script start offset + ZZYY]"""},
    0x16: {"params": 3, "comment":"""XX YY ZZ => (EXIT) go to map number XX; jump to part YY of the script (?); "screen at position" ZZ (???)"""} ,
    0x17: {"params": 1, "comment":"""XX =>  XX: - 0x00 => rest (at an inn)"""} ,
    0x18: {"params": 1, "comment":"""XX => Enter shop menu, XX: shop number (Elcid's item shop, Narvick's spell shop, ...)"""} ,
    0x19: {"params": 0, "comment":"=> Enter church menu"} ,
    0x1A: {"params": 1, "comment":"""XX => Set event bit number XX, (event bits determine what happens on the map, what the NPCs say, ...)"""} ,
    0x1B: {"params": 1, "comment":"XX => Clear event bit number XX"} ,
    0x1C: {"params": 2, "comment":"XX YY => JUMP TO [script start offset + YYXX]"} ,
    0x1D: {"params": 2, "comment":"XX YY => ?"} ,
    0x1E: {"params": 2, "comment":"XX YY => ?"} ,
    0x1F: {"params": 2, "comment":"XX YY => ?"} ,
    0x20: {"params": 2, "comment":"XX YY => Get YY copies of item number 0x00XX"} ,
    0x21: {"params": 2, "comment":"XX YY => Get YY copies of item number 0x01XX"} ,
    0x22: {"params": 2, "comment":"XX YY => Get YYXX GOLD"} ,
    0x23: {"params": 2, "comment":"""XX YY => Party member XX learns the spell YY"""} ,
    0x24: {"params": 2, "comment":"XX YY => ?"},
    0x25: {"params": 2, "comment":"XX YY => ? (remove item from inventory?)"},
    0x26: {"params": 2, "comment":"XX YY => ?"},
    0x27: {"params": 2, "comment":"XX YY => dummy?"},
    0x28: {"params": 0, "comment":"=> ?"},
    0x29: {"params": 3, "comment":"""XX YY ZZ => Randomly increases a "pot. stat+" of character XX by max ZZ?"""},
    0x2A: {"params": 3, "comment":" XX YY ZZ => dummy?"},
    0x2B: {"params": 1, "comment":" XX => Character XX joins the party"},
    0x2C: {"params": 1, "comment":" XX => Character XX leaves the party"},
    0x2D: {"params": 1, "comment":" XX => Character XX appears (?)"},
    0x2E: {"params": 1, "comment":" XX => Character XX disappears (?)"}, # 2 arguments?
    0x2F: {"params": 3, "comment":" XX YY ZZ => ?"},
    0x30: {"params": 2, "comment":" XX YY => Instantly move character XX to pre-defined location YY"},
    0x31: {"params": 2, "comment":""" XX YY => Character XX turns (during conversation) """},
    0x32: {"params": 2, "comment":""" XX YY => Character XX stands still"""},
    0x33: {"params": 2, "comment":" XX YY => Character YY `parcours le trajet` number XX"},
    0x34: {"params": 2, "comment":""" XX YY => Change the sprite of character XX  (YY = new sprite number)"""},
    0x35: {"params": 3, "comment":" XX YY ZZ => ?"},
    0x36: {"params": 1, "comment":" XX => ?"},
    0x37: {"params": 1, "comment":" XX => Pause (duration: XX)"},
    0x38: {"params": 1, "comment":""" XX => Pause X Seconds?"""},
    0x39: {"params": 0, "comment":" => dummy?"},
    0x3A: {"params": 2, "comment":""" XX YY => Show part of the map at coord x = XX y = YY"""},
    0x3B: {"params": 1, "comment":""" XX => Show part of the map at pre-defined position XX """},
    0x3C: {"params": 0, "comment":""" => All party members walk to Maxim and "hide behind" him  (like after a cutscene)"""},
    0x3D: {"params": 1, "comment":""" XX => ? (when I tested it, it instantly "hid" the other  party members behind Maxim)         """},
    0x3E: {"params": 0, "comment":" => ?"},
    0x3F: {"params": 0, "comment":" => ?"},
    0x40: {"params": 0, "comment":" => ?"},
    0x41: {"params": 2, "comment":" XX YY => ?"},
    0x42: {"params": 0, "comment":" => same as 0x00"},
    0x43: {"params": 2, "comment":" XX YY => ?"},
    0x44: {"params": 3, "comment":" XX YY ZZ => ?"},
    0x45: {"params": 3, "comment":" XX YY ZZ => ?"},
    0x46: {"params": 3, "comment":" XX YY ZZ => ?"},
    0x47: {"params": 1, "comment":""" XX => Speech border type"""},
    0x48: {"params": 2, "comment":" XX YY => ?"},
    0x49: {"params": 1, "comment":" XX => ?"},
    0x4A: {"params": 1, "comment":" XX => ? (related to  the appearance of text in text boxes)"},
    0x4B: {"params": 1, "comment":""" XX => Select music for battle?"""},
    0x4C: {"params": 1, "comment":" XX => Sound? (XX: sound number)"},
    0x4D: {"params": 1, "comment":" XX => ? (sound-related?) (can EXIT)"},
    0x4E: {"params": 0, "comment":" => ?"},
    0x4F: {"params": 1, "comment":" XX => dummy?"},
    0x50: {"params": 0, "comment":" => ?"},
    0x51: {"params": 0, "comment":" => ?"},
    0x52: {"params": 1, "comment":" XX => ?"},
    0x53: {"params": 1, "comment":" XX => Boss battle with boss party number XX"},
    0x54: {"params": 1, "comment":""" XX => ? (related to the door in "Tia, are you home?") (Entrance index?)"""},
    0x55: {"params": 1, "comment":" XX => ?"},
    0x56: {"params": 0, "comment":""" => Stop earthquake (screen stops shaking). See opcode 0x5A. Maybe has a more general use."""},
    0x57: {"params": 0, "comment":" => ?"},
    0x58: {"params": 1, "comment":""" XX => Fade to black XX: ? (0x18 after "Would you...go?"/"Yes, sir.")"""},
    0x59: {"params": 1, "comment":""" XX => Luminosity XX: (it seems that each(?) bit has a specific function)"""},
    0x5A: {"params": 3, "comment":" XX YY ZZ => Make an earthquake (screen starts shaking)"},
    0x5B: {"params": 2, "comment":" XX YY => ?"},
    0x5C: {"params": 0, "comment":" => BRK"},
    0x5D: {"params": 0, "comment":" => BRK"},
    0x5E: {"params": 1, "comment":" XX => ? (EXIT)"},
    0x5F: {"params": 1, "comment":" XX => dummy?"},
    0x60: {"params": 2, "comment":" XX YY => ?"},
    0x61: {"params": 0, "comment":" => Maxim speaks spontaneously (also: Erim in the intro)"},
    0x62: {"params": 0, "comment":" => Selan speaks"},
    0x63: {"params": 0, "comment":" => Guy speaks"},
    0x64: {"params": 0, "comment":" => Artea speaks"},
    0x65: {"params": 0, "comment":" => Dekar speaks"},
    0x66: {"params": 0, "comment":" => Tia speaks"},
    0x67: {"params": 0, "comment":" => Lexis speaks"},
    0x68: {"params": 2, "comment":""" XX YY => Character XX use sprite YY (used in map pre-scripts)"""},
    0x69: {"params": 1, "comment":" XX => ?"},
    0x6A: {"params": 3, "comment":""" XX YY YY => If the event flag numberXX is clear  => JUMP TO [script start offset + ZZYY]"""},
    0x6B: {"params": 0, "comment":" => ?"},
    0x6C: {"params": 3, "comment":""" XX YY ZZ => character XX moves; YY: horizontally, ZZ: vertically"""},
    0x6D: {"params": 2, "comment":""" XX YY => display text like "Main programmer" """},
    0x6E: {"params": 2, "comment":""" XX YY => display text like "Akihiro Suzuki" """},
    0x6F: {"params": 1, "comment":""" XX => Change map music"""},
    0x70: {"params": 0, "comment":" => map music off"},
    0x71: {"params": 0, "comment":" => ?"},
    0x72: {"params": 0, "comment":" => ? (sound-related)"},
    0x73: {"params": 2, "comment":""" XX YY => display an animation"""},
    0x74: {"params": 1, "comment":""" XX => Select the background for battles on that map"""},
    0x75: {"params": 0, "comment":" => ?"}, # appears 6 times in vanilla. Before cutScenes?
    0x76: {"params": 0, "comment":" => ?"},
    0x77: {"params": 1, "comment":" XX => ?"},
    0x78: {"params": 0, "comment":" => ?"},
    0x79: {"params": 0, "comment":" => ?"},
    0x7A: {"params": 2, "comment":""" XX YY => The current "frame" of character XX is now "frame" number YY"""},
    0x7B: {"params": 2, "comment":" XX YY => ???"},
    0x7C: {"params": 1, "comment":""" XX => Set "ship upgrades flag"""},
    0x7D: {"params": 1, "comment":""" XX => Set "ship location flag"""},
    0x7E: {"params": 1, "comment":""" XX => Set "ship on map flag"""},
    0x7F: {"params": 1, "comment":""" XX => Set "exit town in ship flag"""},
    0x80: {"params": 1, "comment":""" XX => Set a "ship sprite"""},
    0x81: {"params": 1, "comment":""" XX => A Capsule Monster joins your party"""},
    0x82: {"params": 0, "comment":" => ?"},
    0x83: {"params": 1, "comment":" XX => ? (EXITS)"},
    0x84: {"params": 0, "comment":" => ?"},
    0x85: {"params": 2, "comment":" XX YY => ?"},
    0x86: {"params": 2, "comment":""" XX YY => Character XX moves YY Animation"""},
    0x87: {"params": 2, "comment":" XX YY => ?"},
    0x88: {"params": 0, "comment":" => Set Map Properties"},
    0x89: {"params": 1, "comment":" XX => ?"},
    0x8A: {"params": 0, "comment":" => ?"},
    0x8B: {"params": 3, "comment":" XX YY ZZ => ?"},
    0x8C: {"params": 3, "comment":""" XX YY ZZ =>  ZZ = the sprite that Maxim holds (Gets item)"""},
    0x8D: {"params": 6, "comment":""" X1 X2 X3 X4 X5 X6 => Wave-warping animation of the Sinistrals. Animation is diplayed at pre-defined position X2"""},
    0x8E: {"params": 3, "comment":" XX YY ZZ => ?"},
    0x8F: {"params": 3, "comment":" XX YY ZZ => ?"},
    0x90: {"params": 3, "comment":" XX YY ZZ => ?"},
    0x91: {"params": 2, "comment":" XX YY => ? (affects the last event flag)"},
    0x92: {"params": 1, "comment":" XX => ? (affects the last event flag)"},
    # 0x93: {"params": 3, "comment":" XX YY ZZ => ?"}, # original.
    0x93: {"params": 1, "comment":" XX => ?"}, # Debug Testing.
    0x94: {"params": 3, "comment":" XX YY ZZ =>"},
    0x95: {"params": 3, "comment":" XX YY ZZ => ?"},
    0x96: {"params": 3, "comment":" XX YY ZZ => ?"},
    0x97: {"params": 0, "comment":" => ?"},
    0x98: {"params": 2, "comment":" XX YY => Character XX thunder-warps (at the position YY?)"},
    0x99: {"params": 1, "comment":" XX => ?"},
    0x9A: {"params": 1, "comment":" XX => ?"},
    0x9B: {"params": 5, "comment":""" X1 X2 X3 X4 X5 => ? (related to the palettes or brightness) (could be used for a dance floor)"""},
    0x9C: {"params": 3, "comment":" XX YY ZZ => ?"},
    0x9D: {"params": 1, "comment":" XX => ?"},
    0x9E: {"params": 1, "comment":""" XX => open a dialog window, XX: top to bottom"""},
    0x9F: {"params": 3, "comment":" XX YY ZZ => ?"},
    0xA0: {"params": 6, "comment":" X1 X2 X3 X4 X5 X6 => ?"},
    0xA1: {"params": 2, "comment":" XX YY "},
    0xA2: {"params": 1, "comment":" XX => ? (can EXIT)"},
    0xA3: {"params": 2, "comment":" XX YY => Character XX... moves? >_>"},
    0xA4: {"params": 0, "comment":""" => Pixelation of the screen for a very short time"""},
    0xA5: {"params": 0, "comment":""" => used when you lost a boss battle (0xA5 (00) (00)) => you're at the "load-a-game screen"."""},
    0xA6: {"params": 0, "comment":" => ?"},
    0xA7: {"params": 1, "comment":" XX => ?"},
    0xA8: {"params": 1, "comment":""" XX => 0xA8 00: leave items and all at level 1 (before entering the Ancient cave) 0xA8 01: take back items and stats (after exiting the Ancient cave)"""},
    0xA9: {"params": 2, "comment":" XX YY => ?"},
    0xAA: {"params": 0, "comment":" => ?"},
    0xAB: {"params": 1, "comment":" XX => ? (probably used to check if you have enough dragon eggs for a wish)"},
    0xAC: {"params": 2, "comment":" XX YY => ?"},
    0xAD: {"params": 0, "comment":" => ? (see script of the Egg Dragon Shrine)"},
    0xAE: {"params": 1, "comment":" XX => ?"},
    0xAF: {"params": 2, "comment":""" XX YY => Character XX flickers #YY: related to the "frequency"""},
    0xB0: {"params": 1, "comment":" XX => ?"},
    0xB1: {"params": 2, "comment":" XX YY => ? (affects character number XX)"},
    0xB2: {"params": 2, "comment":" XX YY => ?"},
    0xB3: {"params": 1, "comment":" XX => ? (seems to make the party members face a given direction)"},
    0xB4: {"params": 3, "comment":" XX YY ZZ => ?"},
    0xB5: {"params": 0, "comment":" => ?"},
    0xB6: {"params": 2, "comment":" XX YY => ?"},
    0xB7: {"params": 1, "comment":" XX => ?"},
    0xB8: {"params": 0, "comment":" => ? (can EXIT)"},
    0xB9: {"params": 1, "comment":""" XX => Fill IP bar of party member XX"""},
    0xBA: {"params": 1, "comment":" XX => ?"},
    0xBB: {"params": 0, "comment":" => Show the current report (like the report you can see after the end of the game)"""},
    0xBC: {"params": 0, "comment":" => ? (EXIT)"},
    0xBD: {"params": 2, "comment":" XX YY => ?"},
    0xBE: {"params": 1, "comment":" XX => same as 0x77"},
    0xBF: {"params": 3, "comment":" XX YY ZZ => ?"}, # 4 arguments?
    0xC0: {"params": 3, "comment":" XX YY ZZ => ?"},
    0xC1: {"params": 2, "comment":" XX YY => ?"},
    0xC2: {"params": 6, "comment":" X1 X2 X3 X4 X5 X6 => ?"},
    0xC3: {"params": 6, "comment":" X1 X2 X3 X4 X5 X6 => ?"},
    0xC4: {"params": 2, "comment":""" XX YY => Scroll the screen from current position to position x = XX y = YY  (first horizontally, then vertically)"""},
    0xC5: {"params": 0, "comment":" => ?"},
    0xC6: {"params": 2, "comment":""" XX YY => ? (Displays animation XX on sprite YY?)"""},
    0xC7: {"params": 0, "comment":" => ?"},
    0xC8: {"params": 7, "comment":" X1 X2 X3 X4 X5 X6 X7 => ?"},
    0xC9: {"params": 7, "comment":" X1 X2 X3 X4 X5 X6 X7 => ?"},
    0xCA: {"params": 3, "comment":" XX YY ZZ => ?"},
    0xCB: {"params": 1, "comment":" XX => ?"},
    0xCC: {"params": 1, "comment":" => ?"},
    # Additions by HEROgold
    # 0xCE: {"params": 0, "comment":" => ? (text related?)"},
    # (EXIT: exits the L2SASM program (by example with BRL 0x009DB0))
    # Flow-control instructions: 0x12, 0x1C, 0x14, 0x15, 0x6A
    # "Enter text mode" instructions: 0x08, 0x13, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67, 0x6D, 0x6E, 0x9E
    # "Exit text mode" instructions: 0x00, 0x01, 0x0B

    # Script data format:
    # Offset + 0x0000:
    # 50 48 
    # Offset + 0x0002:
    # 6 pointers (2 bytes) to subscripts
}
FLOW_CONTROL = [0x12, 0x1C, 0x14, 0x15, 0x6A]
ENTER_TEXT_MODE = [0x08, 0x13, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67, 0x6D, 0x6E, 0x9E]
EXIT_TEXT_MODE = [0x00, 0x01, 0x0B]
SPACE = " "
VALID_ASCII_CHARACTERS = ascii_letters + digits + punctuation + SPACE

class TextScript:

    def __init__(self, pointer: int) -> None:
        self.pointer = pointer

    @property
    @restore_pointer
    def pre_data(self):
        pointer = self.pointer - 0x1000
        assert pointer >= 0
        read_file.seek(pointer)
        return read_file.read(0x1000)

    @restore_pointer
    def read(self):
        read_file.seek(self.pointer)
        b = b""
        while True:
            code = read_file.read(1)
            opcode = code[0]
            b += code
            if opcode in EXIT_TEXT_MODE:
                break
        return b

    @staticmethod
    def _find_word_index(code: int, index: int) -> int:
        return index + (0x100 * (code-5))


    def encode(self, text: str) -> bytes:
        # TODO: Find if a word in text exists in the Word class.
        # If it does, encode it as a compressed word (index). as decoded below.
        ...

    def decode(self, text: bytes) -> tuple[str, bytes]:
        assert text[0] in [5, 6]
        index = self._find_word_index(text[0], text[1])
        return Word.from_index(index).word, text[2:]

    # TODO: parse the rest of the text. Below line displays compressed to full text.
    # b'\x05P \x88 Elc\xf2!\x00' > "Welcome to Elcid!"
    def pretty_read(self):
        """Decompresses words from a text, and returns the text."""
        text = self.read()
        result = ""

        while text:
            # Parse 05/06 shifts to words.
            if text[0] in {5, 6}:
                word, text = self.decode(text)
                result += word
                continue
            if (
                text[0] < 128
                and (letter := text[:1].decode("ascii"))
                and letter in VALID_ASCII_CHARACTERS
            ):
                # Ascii decodable and decoded in ascii.
                result += letter
                text = text[1:]
                continue
            result += f"<{text[0]:02X}>"
            text = text[1:]
        return result

class EventScriptV2:
    _data: bytes | None = None

    def __init__(self, pointer: int, size: int) -> None:
        self.pointer = pointer
        self.size = size

    @property
    def data(self) -> bytes:
        if self._data is None:
            self._data = read_file.read(self.size)
        return self.data

# TODO: Add classes to represent the different opcodes.
# Those should be able to be used, to write custom scripts?
# TODO: when reading, instead of appending to stack,
# create a tree like structure to represent the script.
# So EventPatchParser should contain children of Self.
class EventScript:
    _seen: list[int]

    def __init__(self, base_pointer: int, offset: int) -> None:
        self.logger = logging.getLogger(f"{iris.name}.{__class__.__name__}")
        self.base_pointer = base_pointer
        self.offset = offset
        self._script: list[bytes] = []
        self._pretty_script: list[tuple[str, bytes, str]] = []
        self._children = set()
        self._parent: Self | None = None
        self._text_mode = False

    @property
    def pointer(self) -> int:
        return self.base_pointer + self.offset
    @property
    def size(self) -> int:
        child_size = sum([child.size for child in self.children])
        return len(self._script) + child_size
    @property
    def children(self) -> set[Self]:
        return self._children
    @property
    def parent(self) -> Self | None:
        return self._parent
    @parent.setter
    def parent(self, parent: Self | None) -> None:
        self._parent = parent
        if parent:
            parent._children.add(self)
            self._seen = parent._seen

    # TODO: implement a writing method.
    # should be able to write the script back, and update pointers etc.
    # When writing, hitting a branch should keep track of how many branches we've seen
    # and then index using that number on self._children to get that branch's script.
    # From there we can modify pointers as required.

    @restore_pointer
    def read(self, offset: int = 0):
        # TODO CRITICAL: Rethink the reading of the script.
        if not hasattr(self, "_seen"):
            self._seen = [self.pointer + offset]
        self._stack: list[int] = []
        read_file.seek(self.pointer)

        while True:
            byte = read_file.read(1)
            _address = read_file.tell()
            offset += 1
            op_code = int.from_bytes(byte)
            description = op_codes[op_code]['comment']
            n_args = op_codes[op_code]['params']
            args = read_file.read(n_args)
            offset += n_args

            if "BRK" in description:
                self.logger.warning(f"BRK found in EventScript {self.pointer} at {offset=}, Address: {self.pointer + offset}")
                # returns to parent script?
            if self.pointer + offset in self._seen:
                self.logger.warning(f"Repeat detected in EventScript {self.pointer=} at {offset=}, Address: {self.base_pointer + offset}")
                break

            self._script.append(byte)
            self._script.append(args)
            self._pretty_script.append((hex(op_code), args, description))

            if op_code in [0x10, 0x12]:
                print(f"To Implement: {op_code=}, {args=}")

            if op_code in ENTER_TEXT_MODE and self._text_mode is False:
                self._text_mode = True # Debugging purposes.
            elif op_code in EXIT_TEXT_MODE and self._text_mode is True:
                self._text_mode = False # Debugging purposes.

            if op_code == 0x00:
                if len(self._stack) == 0:
                    break
                read_file.seek(self._stack.pop())
            elif op_code == 0x02: # Breaks
                pass
            elif op_code == 0x06:
                if args[1] != 0x20:
                    # What is args[1] == 0x0A? (relative pointer jump)
                    print(args) # Figure out the meaning when arg[1] != 0x20
            elif op_code == 0x08:
                text = TextScript(self.pointer + offset) # TODO: figure out how to set uncompressed text.
                b = text.read()
                offset += len(b)
                read_file.seek(self.pointer + offset)
            elif op_code == 0x0A:
                # TODO: verify jump address
                jump = self.pointer + int.from_bytes(args, byteorder='little')
                self._branch(jump)
            # elif op_code == 0x12:
            #     count = args[1]
            #     for _ in reversed(range(count)):
            #         pointer = read_little_int(read_file, POINTER_SIZE)
            #         self._stack.append(pointer)
            #         offset += POINTER_SIZE
            elif op_code == 0x12:
                # TODO CRITICAL: This is where you left of! Check if the branching is correct.
                # 0x0003C084 or 245892 is the start of the event. (self.pointer)
                # 0x0003c096 is the start of the first branch.
                # Branch on variable
                pointer_count = args[0] # Perhaps this is the index of _pointers to follow?
                _pointers = [args[1]]
                if pointer_count < 0:
                    raise ValueError(f"Pointer count is negative: {pointer_count}")
                restore = read_file.tell()
                for i in range(pointer_count):
                    _pointer = int.from_bytes(read_file.read(2), byteorder='little')
                    _pointers.append(_pointer)
                    self._branch(_pointer) # TODO: Verify this is correct.
                assert pointer_count+1 == len(_pointers)

                # Maybe we branch/jump, then do something else?
                print(read_file.tell() + _pointers[pointer_count])
                read_file.seek(read_file.tell() + _pointers[pointer_count])
                self._branch(self.pointer + _pointers[pointer_count])
                # offset += _pointers[pointer_count]
                continue
                read_file.seek(restore)
                if pointer_count == 0:
                    read_file.seek(read_file.tell() - 1)
                print(pointer_count, _pointers[pointer_count])
            elif op_code == 0x14:
                offset = self.instruction_parsing(offset, args)
            elif op_code == 0x15:
                jump = int.from_bytes(args[1:], byteorder='little')
                self._branch(jump)
            elif op_code == 0x16:
                # TODO: find out if this has a jump?
                # stack.append(self.pointer + args[1])
                pass
            elif op_code in [0x1C, 0x6A]:
                jump = int.from_bytes(args, byteorder='little')
                self._branch(jump)
            elif op_code in [0x13, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67, 0x6D, 0x6E, 0x9E]:
                if op_code == 0x13:
                    _npc_index = args[0] # Excess? Debug code.
                elif op_code in [0x6D, 0x6E, 0x9E]:
                    _position = args[0]
                text_script = TextScript(self.pointer + offset)
                # TODO: refine the parsing of compressed text.
                # if self.pointer == 245892:
                #     text_script.pretty_read()
                b = text_script.read()
                offset += len(b)
                read_file.seek(self.pointer + offset)
                print(b)

            elif op_code == 0xCC:
                tell = read_file.tell()
                data: list[bytes] = []
                while True:
                    byte = read_file.read(1)
                    data.append(byte)
                    if byte == b'\x20':
                        break
                print((tell, data))
                read_file.seek(tell)
            elif op_code in []:
                # The listed opcodes, don't require special handling. or are unknown.
                # These usually are opcode + 1 byte of arg.
                continue
            else:
                self.logger.warning(f"Warning! Unhandled opcode: {op_code=:#02x} {args=}")

        assert len(self._stack) == 0, f"Script restore stack not empty: {self._stack}"
        s = "\n"
        for i in self._pretty_script:
            s += f"    {i[0]} + {i[1]}: {i[2]}\n"
        self.logger.debug(s)

    def instruction_parsing(self, offset: int, args: bytes):
        # TODO: figure out a better name for this method.
        flag = None
        while True:
            if flag is None:
                flag = args[0]
            else:
                flag = read_little_int(read_file, 1)
                offset += 1

            if flag == 0xff:
                break
            elif flag & 0xf0 == 0xf0:
                assert len(args) == 1
                assert flag in {0xf0, 0xf8}
                        # 0xf0 Monster on button
                        # 0xf8 if NPC state
            elif flag & 0xf0 == 0xc0:
                assert len(args) == 1
                assert flag in {0xc0, 0xc2}
                        # 0xc0 Check item possessed exactly number
                        # 0xc2 Check item possessed GTE
                item_index = read_file.read(2)
                offset += 2
                item_number = read_file.read(2)
                offset += 2
                self._script.append(item_index)
                self._script.append(item_number)
            elif flag & 0xf0 == 0x10:
                assert len(args) == 1
                assert flag in {0x10, 0x12}
                        # 0x10 Equals
                        # 0x12 GTE
                _1 = read_file.read(1)
                offset += 1
                _2 = read_file.read(1)
                offset += 1
                self._script += [_1, _2]
            elif flag & 0xe0 == 0x20:
                assert flag in {0x20, 0x30}
                        # 0x20 Branch if True
                        # 0x30 Branch if False
                pointer_offset = read_file.read(2)
                offset += 2
                _pointer = self.pointer + int.from_bytes(pointer_offset, "little")
                self._script.append(pointer_offset)
            else:
                assert flag in {0x00, 0x01, 0x40, 0x41, 0x80, 0x81}
                        # 0x01 NOT
                        # 0x40 OR
                        # 0x80 AND
                read = read_file.read(1)
                offset += 1
                self._script.append(read)
        return offset

    @restore_pointer
    def _branch(self, jump: int):
        branch_pointer = self.base_pointer + jump
        if branch_pointer in self._seen:
            self.logger.warning(f"Repeat at branch detected in EventScript {self.pointer=} at {jump=}")
            return
        self._seen.append(self.base_pointer + jump)
        child = EventScript(self.base_pointer, jump)
        child.parent = self
        child.read()
