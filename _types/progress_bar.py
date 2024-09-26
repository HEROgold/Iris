import math
from os import get_terminal_size


class ProgressBar:
    _ts = get_terminal_size()
    MAX_WIDTH = _ts.columns
    MAX_HEIGHT = _ts.lines
    SPACE = " "
    # Editable
    message = "Progress:"
    start = "["
    end = "]"
    arrow = ">"
    bar = "="

    def __init__(self, total: int) -> None:
        self.total = total
        self.current = 0

    def update(self, current: int) -> None:
        self.current = current

    def __str__(self) -> str:
        bar_room = (
            self.MAX_WIDTH
            - len(self.message)
            - len(self.start)
            - len(self.arrow)
            - len(self.end)
        )
        scale = self.current / self.total

        bar_count = math.floor(bar_room * scale)
        bar = self.bar * (bar_count // len(self.bar))

        air_count = (math.floor(bar_room - len(bar)) - len(self.end))
        air = self.SPACE * air_count

        # if scale == 0, make sure the len our return is the same as any other scale
        end = self.end + self.SPACE if int(scale) != 0 else self.end 
        return f"{self.message}{self.start}{bar}{self.arrow}{air}{end}"
