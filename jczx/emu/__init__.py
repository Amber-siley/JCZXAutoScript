import os
from .base import EmulatorStrategy
from .mumu import MuMuStrategy

_STRATEGY_MAP = {
    "MuMuManager": MuMuStrategy,
}


def get_emu_strategy(path: str, startupinfo) -> EmulatorStrategy | None:
    name = os.path.basename(path)
    for keyword, strategy_cls in _STRATEGY_MAP.items():
        if keyword in name:
            return strategy_cls(path, startupinfo)
    return None
