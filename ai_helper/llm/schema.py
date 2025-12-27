from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class ToolCall:
    name: str
    arguments: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "arguments": dict(self.arguments)}
