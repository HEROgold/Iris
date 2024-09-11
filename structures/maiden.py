
class Maiden:
    def __init__(
        self,
        name: str,
        display_name: str,
        flag: int,
        sister_flag_1: int,
        sister_flag_2: int,
    ) -> None:
        self.name = name
        self.maiden_name = display_name
        self.my_maiden_flag = flag
        self.maiden_flag1 = sister_flag_1
        self.maiden_flag2 = sister_flag_2

Lisa = Maiden("lisa","Lisa",0x1a,0x1b,0x1c)
Marie = Maiden("marie","Marie",0x1b,0x1c,0x1a)
Clare = Maiden("clare","Clare",0x1c,0x1a,0x1b)
