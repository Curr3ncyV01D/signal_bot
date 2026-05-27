from abc import ABC, abstractmethod

class BaseAggregator(ABC):
    @abstractmethod
    def cleanup_task(self):
        """Каждый агрегатор должен уметь чистить свою память."""
        pass