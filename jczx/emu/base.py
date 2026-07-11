from abc import ABC, abstractmethod


class EmulatorStrategy(ABC):
    @abstractmethod
    def launch(self, index: str) -> bool:
        ...

    @abstractmethod
    def shutdown(self, index: str) -> bool:
        ...

    @abstractmethod
    def wait_started(self, index: str, timeout: int = 120) -> bool:
        ...
