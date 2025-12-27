from __future__ import annotations

import asyncio
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core import logger
from .schema import ToolCall


class GrokAdapter:
    def __init__(self, adapter_path: Optional[str], api_key: Optional[str] = None, mock: bool = False) -> None:
        self.adapter_path = adapter_path
        self.api_key = api_key
        self.mock = mock
        self._client = None

    def _resolve_root(self) -> Optional[Path]:
        if not self.adapter_path:
            return None

        path = Path(self.adapter_path).expanduser().resolve()
        if path.name != "grok.py":
            raise ValueError("Adapter path must point to grok.py")

        llm_dir = path.parent
        init_file = llm_dir / "__init__.py"
        if not init_file.exists():
            raise ValueError("Adapter path is not inside a Python package")

        return llm_dir.parent

    def _load_client(self) -> None:
        if self._client or self.mock:
            return

        root = self._resolve_root()
        if root is None:
            raise ValueError("Adapter path is required")

        root_str = str(root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)

        module = importlib.import_module("llm_interfaces.grok")
        self._client = module.GrokInterface(api_key=self.api_key)

    def request_tool_calls(
        self,
        prompt: str,
        selection: Dict[str, Any],
        tools: Optional[List[Dict[str, Any]]] = None,
        use_mock: Optional[bool] = None,
    ) -> List[ToolCall]:
        if use_mock is None:
            use_mock = self.mock

        if use_mock:
            return self._mock_tool_calls(prompt)

        self._load_client()

        request_payload = {
            "prompt": prompt,
            "selection": selection,
            "tools": tools or [],
        }
        messages = [
            {
                "role": "system",
                "content": "You are a CAD assistant. Return JSON with tool_calls only.",
            },
            {
                "role": "user",
                "content": json.dumps(request_payload),
            },
        ]

        response_text = _run_async(self._client.generate(messages=messages))
        data = json.loads(response_text)
        return _parse_tool_calls(data)

    def _mock_tool_calls(self, prompt: str) -> List[ToolCall]:
        logger.logger.info("Mock Grok response for prompt: %s", prompt)
        return [
            ToolCall(
                name="transform_object",
                arguments={"name": "Cube", "location": [0.0, 0.0, 1.0]},
            )
        ]


def _parse_tool_calls(data: Dict[str, Any]) -> List[ToolCall]:
    calls = []
    for item in data.get("tool_calls", []):
        name = str(item.get("name", ""))
        args = item.get("arguments") or {}
        if name:
            calls.append(ToolCall(name=name, arguments=dict(args)))
    return calls


def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        raise RuntimeError("Async loop already running; use async integration")

    return asyncio.run(coro)
