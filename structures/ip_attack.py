from typing import Self

from abc_.pointers import Pointer
from enums.flags import Targeting, TargetingCursor
from helpers.bits import read_little_int
from helpers.files import read_file, write_file
from tables import IPAttackObject


class IPAttack(Pointer):
    def __init__(
        self,
        effect: int, # L2BASM subroutine number. (2 bytes)
        animation: int,
        target_cursor: TargetingCursor,
        target_mode: int,
        ip_cost: int,
        name: str,
    ) -> None:
        self.name = name
        self.ip_cost = ip_cost
        self.target_cursor = target_cursor
        self.target_mode = target_mode
        self.effect = effect
        self.animation = animation

    @classmethod
    def from_pointer(cls, pointer: int) -> Self:
        read_file.seek(pointer)
        effect = read_little_int(read_file, IPAttackObject.effect)
        animation = read_little_int(read_file, IPAttackObject.animation)
        target_cursor = TargetingCursor(read_little_int(read_file, IPAttackObject.target_cursor))
        target_mode = Targeting(read_little_int(read_file, IPAttackObject.target_mode))
        ip_cost = read_little_int(read_file, IPAttackObject.ip_cost) # 0x00 - 0xFF > 0% > 100%

        name = ""
        while True:
            char = read_file.read(1)
            if char == b"\x00":
                break
            name += char.decode("ascii")

        inst = cls(effect, animation, target_cursor, target_mode, ip_cost, name)
        super().__init__(inst, pointer)
        return inst

    @property
    def description(self) -> str:
        """Not decoded yet: the description text is compressed with dictionary 2.

        Headerless offsets (info/L2_IPDataFormat.txt lists them headered, 0x200 higher):
        0xB8462-0xB85B3: 169 IP description pointers, each relative to 0xB8000.
        0xB85B4-0xBB0A0: item / spell / IP description text.
        The IP effect scripts are a separate table at 0xAF1EF (structures/ip_effect.py).
        """
        # TODO: decompress the description. Same goes for item descriptions.
        return ""

    def write(self) -> None:
        write_file.seek(self.pointer)
        write_file.write(self.effect.to_bytes(IPAttackObject.effect, "little"))
        write_file.write(self.animation.to_bytes(IPAttackObject.animation, "little"))
        write_file.write(self.target_cursor.value.to_bytes(IPAttackObject.target_cursor, "little"))
        write_file.write(self.target_mode.to_bytes(IPAttackObject.target_mode, "little"))
        write_file.write(self.ip_cost.to_bytes(IPAttackObject.ip_cost, "little"))
        write_file.write(self.name.encode("ascii"))
        write_file.write(b"\x00")
