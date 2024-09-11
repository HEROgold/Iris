from enums.flags import Targeting, TargetingCursor
from helpers.files import read_file, write_file
from typing import Self
from abc_.pointers import Pointer
from helpers.bits import read_little_int
from tables import IPAttackObject

class IPAttack(Pointer):
    def __init__(
        self,
        effect: int, # L2BASM subroutine number. (2 bytes)
        animation: int,
        target_cursor: TargetingCursor,
        target_mode: int,
        ip_cost: int,
        name: str
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
        """
        -----------------------------------------------------------------------
        IP descriptions
        -----------------------------------------------------------------------
        [$0B8662, $0B87B3]:  pointers to IP descriptions (2 bytes, little-endian)
        [$0B87B4, $0BB2A0]:  item / spell / IP descriptions
        The IP descriptions are compressed.
        -----------------------------------------------------------------------
        IP effects
        -----------------------------------------------------------------------
        [$0AF3EF, $0AF508]:  pointers to data at [$0AF509] (2 bytes, little-endian)
                            282 bytes => 141
                            Add $0AF3EF to the pointers to find the offsets
                            of the L2BASM scripts for IP effects.
        [$0AF509, $0AFC5A]:  L2BASM scripts for IP effects.
        Each L2BASM script is preceeded by $FF.
        """
        # TODO: decompress the description. Same goes for item descriptions.
        pointers = range(0xB8662, 0xB87B3, 2)
        _data = [
            0x0AF509 + pointer
            for pointer in pointers
        ]
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