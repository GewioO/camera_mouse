from abc import ABC, abstractmethod


class ModuleRunner(ABC):
    """
    One active input module (hand / forearm / eyes / …)
    """

    @abstractmethod
    def process(self, frame):
        raise NotImplementedError

    def close(self):
        pass
