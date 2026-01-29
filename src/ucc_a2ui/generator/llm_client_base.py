from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class LLMResponse:
    content: str


class LLMClientBase:
    def complete(self, messages: List[dict]) -> LLMResponse:
        raise NotImplementedError
