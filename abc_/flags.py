import random
from enums.flags import EquipTypes, Flags, Usability
from errors import AlreadyScaledError, CompatibilityError


from abc import ABC, abstractmethod



class Flagged(ABC):
    def __init__(self) -> None:
        self.flags = Flags(0)
        self._check_compatibility()

    def has_flag(self, flag: Flags) -> bool:
        return flag in self.flags

    def add_flag(self, flag: Flags) -> None:
        self.flags += flag

    def remove_flag(self, flag: Flags) -> None:
        self.flags -= flag

    def _check_compatibility(self) -> None:
        incompatibles = {
            Flags.NOTHING_PERSONNEL_KID: [Flags.HOLIDAY],
            Flags.EVERYWHERE: [Flags.ANYWHERE],
        }
        for flag in incompatibles:
            for incompatible in incompatibles[flag]:
                if flag in self.flags and incompatible in self.flags:
                    raise CompatibilityError(f"{flag.name} is not compatible with {incompatibles[flag]}.")


class Equipable(Flagged):
    def __init__(self, equip_types: EquipTypes) -> None:
        Flagged.__init__(self)
        self.equip_types = equip_types

        if self.has_flag(Flags.EVERYWHERE):
            self.equip_types = EquipTypes.ALL
        if self.has_flag(Flags.ANYWHERE):
            # According to absynnonym on terrorwave.
            raise CompatibilityError("ANYWHERE flag is not compatible with Lufia II.")
            # target = 0
            # while target == 0:
            #     target = random.randrange(EquipTypes(0), EquipTypes.ALL)
            # self.equip_types = EquipTypes(target)


class Scalable(ABC):
    def __init__(self) -> None:
        self._scale = 1
        self._scaled = False
        self._scalable = False

    @property
    def scale(self) -> float:
        return self._scale

    @scale.setter
    def scale(self, value: float) -> None:
        self._scale = value
        self._scaled = True

    def _check_scale(self):
        if not self._scalable:
            raise CompatibilityError(f"{self.__class__.__name__} is not scalable.")
        if self._scaled:
            raise AlreadyScaledError(f"{self.__class__.__name__} has already been scaled.")

    @abstractmethod
    def apply_scale(self) -> None:
        pass

    @abstractmethod
    def undo_scale(self) -> None:
        pass


class Usable(Flagged):
    def __init__(self, usability: Usability) -> None:
        self.usability = usability

        if self.has_flag(Flags.EVERYWHERE):
            self.equip_types = Usability.ALL
        if self.has_flag(Flags.ANYWHERE):
            # According to absynnonym on terrorwave.
            raise CompatibilityError("ANYWHERE flag is not compatible with Lufia II.")
            target = 0
            while target == 0:
                target = random.randrange(EquipTypes(0), EquipTypes.ALL)
            self.equip_types = EquipTypes(target)
