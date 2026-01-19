from abc import ABC, abstractmethod
from core.intent import Intent


class BaseExecutor(ABC):
    """
    Base contract for all executors.
    Executors take an Intent and return a response dict.
    No routing, no parsing, no side effects here.
    """

    @abstractmethod
    async def execute(self, intent: Intent) -> dict:
        pass
