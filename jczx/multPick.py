from typing import List

from pick import Option, Picker

SYMBOL_CIRCLE_FILLED = "[●]"
SYMBOL_CIRCLE_EMPTY = "[○]"

class MultiPicker(Picker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def choose_index(self, index: int):
        if index < 0 or index >= len(self.options):
            raise ValueError(f"Invalid index {index}")
        if index not in self.selected_indexes:
            self.selected_indexes.append(index)

    def get_option_lines(self) -> List[str]:
        lines: List[str] = []
        for index, option in enumerate(self.options):
            if index == self.index:
                prefix = self.indicator
            else:
                prefix = len(self.indicator) * " "
            if self.multiselect:
                symbol = (
                    SYMBOL_CIRCLE_FILLED
                    if index in self.selected_indexes
                    else SYMBOL_CIRCLE_EMPTY
                )
                prefix = f"{prefix} {symbol}"
            option_as_str = option.label if isinstance(option, Option) else option
            lines.append(f"{prefix} {option_as_str}")
        return lines

def pick(
    options: list = None,
    title: str = None,
    indicator: str = ">",
    select_indexs: list[int] = None,
    multiselect: bool = False,
    *args,
    **kwargs,
):
    picker: MultiPicker = MultiPicker(options, title, indicator, multiselect, *args, **kwargs)
    if select_indexs:
        picker.multiselect = True
        for index in select_indexs:
            picker.choose_index(index)
    return picker.start()