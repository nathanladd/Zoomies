from abc import ABC, abstractmethod
from typing import Any


class BaseGame(ABC):
    """Abstract base class for all game modules."""

    @abstractmethod
    async def on_player_join(self, player_id: int, name: str) -> dict[str, Any]:
        ...

    @abstractmethod
    async def on_start(self) -> dict[str, Any]:
        ...

    @abstractmethod
    async def on_next_question(self) -> dict[str, Any] | None:
        ...

    @abstractmethod
    async def on_submit_answer(self, player_id: int, choice: str, elapsed_ms: int) -> dict[str, Any]:
        ...

    @abstractmethod
    async def on_reveal(self) -> dict[str, Any]:
        ...

    @abstractmethod
    async def on_end(self) -> dict[str, Any]:
        ...

    @abstractmethod
    def get_status(self) -> dict[str, Any]:
        ...
