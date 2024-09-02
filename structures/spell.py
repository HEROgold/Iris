from _types.objects import Cache
from errors import SpellNotFound
from helpers.files import read_file, write_file
from typing import Self
from enums.flags import CastableSpells
from helpers.bits import read_little_int
from tables import SpellObject
from abc_.pointers import Pointer


SPELLS_ADDRESS = 0x000AFAAB


class Spell(Pointer):
    _int_cache = Cache[int, Self]()
    _name_cache = Cache[str, Self]()

    def __init__(
        self,
        name: str,
        unk1: int,
        element: int,
        characters: CastableSpells,
        unk4: int,
        mp_cost: int,
        zero: int,
        price: int,
    ) -> None:
        self.name = name
        self.unk1 = unk1
        self.element = element
        self.characters = characters
        self.unk4 = unk4
        self.mp_cost = mp_cost
        self.zero = zero
        self.price = price

    @classmethod
    def from_name(cls, name: str) -> Self:
        if inst := cls._name_cache.from_cache(name):
            return inst

        original = read_file.tell()
        read_file.seek(SPELLS_ADDRESS)
        for pointer in SpellObject.pointers:
            inst = cls.from_pointer(pointer)
            if inst.name == name:
                read_file.seek(original)
                cls._name_cache.to_cache(name, inst)
                return inst
        else:
            raise SpellNotFound(f"Spell with name {name} not found.")

    @classmethod
    def from_index(cls, index: int) -> Self:
        if inst := cls._int_cache.from_cache(index):
            return inst

        original = read_file.tell()
        read_file.seek(SPELLS_ADDRESS)
        for i, pointer in enumerate(SpellObject.pointers):
            if i == index:
                read_file.seek(original)
                inst = cls.from_pointer(pointer)
                cls._int_cache.to_cache(index, inst)
                return inst
        else:
            raise SpellNotFound(f"Spell with index {index} not found.")

    @classmethod
    def from_pointer(cls, pointer: int) -> Self:
        """
        Get's a Spell from a pointer in a file.
        
        Parameters
        -----------
        :param:`pointer`: :class:`int`
            The pointer to the spell.
        :param:`file`: :class:`_type_`
            The file to get the spell from.
        
        Returns
        -------
        :class:`Self`
            A spell object.
        """
        original = read_file.tell()
        read_file.seek(pointer)

        name = read_file.read(SpellObject.name_text).decode() # type: ignore
        _unk1 = read_little_int(read_file, SpellObject.unk1)
        element = read_little_int(read_file, SpellObject.element)
        characters = CastableSpells.from_byte(read_file.read(1))
        _unk4 = read_little_int(read_file, SpellObject.unk4)
        mp_cost = read_little_int(read_file, SpellObject.mp_cost)
        _zero = read_little_int(read_file, SpellObject.zero)
        price = read_little_int(read_file, SpellObject.price)

        inst = cls(
            name,
            _unk1,
            element,
            characters,
            _unk4,
            mp_cost,
            _zero,
            price
        )
        super().__init__(inst, pointer)
        read_file.seek(original)
        return inst

    @property
    def index(self) -> int:
        return SpellObject.pointers.index(self.pointer)

    def write(self):
        write_file.seek(self.pointer)

        write_file.write(self.name.encode())
        write_file.write(self.unk1.to_bytes())
        write_file.write(self.element.to_bytes())
        write_file.write(self.characters.to_bytes())
        write_file.write(self.unk4.to_bytes())
        write_file.write(self.mp_cost.to_bytes())
        write_file.write(self.zero.to_bytes(2, "little"))
        write_file.write(self.price.to_bytes(2, "little"))
