
class RewardItem:
    def __init__(
        self,
        name: str,
        display_name: str,
        item_index: int,
        icon_code: str | int
    ) -> None:
        self.name = name
        self.item_display_name = display_name
        self.item_index = item_index
        self.item_icon_code = icon_code

class RewardMaiden:
    def __init__(
        self,
        name: str,
        display_name: str,
        flag: int,
        sister_flag1: int,
        sister_flag2: int
    ) -> None:
        pass
