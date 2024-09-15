
class RewardItem:
    """A reward item that can be given to the player.
    This is used when you receive and item from a chest, NPC, etc."""
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
