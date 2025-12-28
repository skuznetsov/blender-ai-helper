from __future__ import annotations

import asyncio
import base64
import importlib
import json
import mimetypes
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from ..core import logger
from .schema import ToolCall


class GrokAdapter:
    def __init__(
        self,
        adapter_path: Optional[str],
        api_key: Optional[str] = None,
        mock: bool = False,
        model: Optional[str] = None,
        vision_model: Optional[str] = None,
    ) -> None:
        self.adapter_path = adapter_path
        self.api_key = api_key
        self.mock = mock
        self.model = model
        self.vision_model = vision_model
        self._client = None
        self._client_model = None

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

    def _load_client(self, model_name: Optional[str] = None) -> None:
        if self.mock:
            return

        root = self._resolve_root()
        if root is None:
            raise ValueError("Adapter path is required")

        root_str = str(root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)

        if self._client and self._client_model == model_name:
            return

        module = importlib.import_module("llm_interfaces.grok")
        self._client = module.GrokInterface(api_key=self.api_key, model_name=model_name)
        self._client_model = model_name

    def request_tool_calls(
        self,
        prompt: str,
        selection: Dict[str, Any],
        tools: Optional[List[Dict[str, Any]]] = None,
        use_mock: Optional[bool] = None,
        image_path: Optional[str] = None,
        image_notes: Optional[str] = None,
        upload_command: Optional[str] = None,
        upload_timeout: Optional[int] = None,
    ) -> List[ToolCall]:
        if use_mock is None:
            use_mock = self.mock

        has_image = bool(image_path)
        model_name = None
        if not use_mock:
            if has_image:
                model_name = self.vision_model or os.getenv("GROK_VISION_MODEL") or "grok-4-1-fast-reasoning"
            else:
                model_name = self.model or os.getenv("GROK_MODEL")

        image_payload = None
        image_ref = None
        used_data_url = False
        if image_path:
            if _is_url(image_path):
                image_ref = image_path
            else:
                if upload_command:
                    image_ref = _run_upload_command(upload_command, image_path, upload_timeout)
                if not image_ref:
                    if model_name and not _supports_data_url(model_name):
                        raise ValueError(
                            "Vision model requires HTTPS URL. Set Image URL or provide Vision Upload Command."
                        )
                    max_bytes = 20 * 1024 * 1024 if _supports_data_url(model_name) else 2 * 1024 * 1024
                    allowed_mimes = ("image/jpeg", "image/png") if _supports_data_url(model_name) else None
                    image_payload = _load_image_payload(image_path, max_bytes=max_bytes, allowed_mimes=allowed_mimes)
                    image_ref = _payload_to_data_url(image_payload)
                    used_data_url = True

        if use_mock:
            if image_ref and image_payload is None:
                image_payload = {"url": image_ref}
            return self._mock_tool_calls(prompt, image_payload=image_payload, image_notes=image_notes)

        self._load_client(model_name)

        use_vision = image_ref is not None and hasattr(self._client, "generate_with_vision")
        request_payload = {
            "prompt": prompt,
            "selection": selection,
            "tools": tools or [],
        }
        if image_ref and not use_vision:
            if image_payload:
                request_payload["image"] = image_payload
            else:
                request_payload["image_url"] = image_ref
        if image_notes:
            request_payload["image_notes"] = image_notes
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a CAD assistant. Return JSON with tool_calls only. "
                    "Use add_line/add_circle/add_arc/add_polyline/add_rectangle on the XY plane for sketches. "
                    "Use edit_arc and edit_rectangle to modify arcs/rectangles (prefer tag targeting). "
                    "Label geometry with tags and call select_sketch_entities before constraints. "
                    "If an image is provided, infer a matching 2D sketch."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(request_payload),
            },
        ]

        if use_vision:
            try:
                response_text = _run_async(self._client.generate_with_vision(messages=messages, images=[image_ref]))
            except Exception as exc:
                if used_data_url and upload_command and _should_retry_with_upload(exc):
                    image_ref = _run_upload_command(upload_command, image_path, upload_timeout)
                    response_text = _run_async(self._client.generate_with_vision(messages=messages, images=[image_ref]))
                else:
                    raise
        else:
            response_text = _run_async(self._client.generate(messages=messages))
        data = json.loads(response_text)
        return _parse_tool_calls(data)

    def _mock_tool_calls(
        self,
        prompt: str,
        image_payload: Optional[Dict[str, Any]] = None,
        image_notes: Optional[str] = None,
    ) -> List[ToolCall]:
        logger.logger.info("Mock Grok response for prompt length: %d", len(prompt))
        prompt_lower = prompt.lower()
        if image_payload:
            prompt_lower += " image"
        if image_notes:
            prompt_lower += f" {image_notes.lower()}"

        if "edit rectangle" in prompt_lower or "edit_rectangle" in prompt_lower:
            return [
                ToolCall(
                    name="edit_rectangle",
                    arguments={
                        "tag": "rect",
                        "width": 4.0,
                        "height": 2.0,
                        "rotation_deg": 15.0,
                    },
                )
            ]
        if "rectangle" in prompt_lower:
            return [
                ToolCall(
                    name="add_rectangle",
                    arguments={"center_x": 0.0, "center_y": 0.0, "width": 2.0, "height": 1.0, "tag": "rect"},
                )
            ]
        if "arc" in prompt_lower:
            return [
                ToolCall(
                    name="add_arc",
                    arguments={
                        "center_x": 0.0,
                        "center_y": 0.0,
                        "radius": 1.0,
                        "start_angle": 0.0,
                        "end_angle": 90.0,
                        "tag": "arc",
                    },
                )
            ]
        if "edit arc" in prompt_lower or "edit_arc" in prompt_lower:
            return [
                ToolCall(
                    name="edit_arc",
                    arguments={
                        "tag": "arc",
                        "radius": 2.0,
                        "start_angle": 0.0,
                        "end_angle": 180.0,
                    },
                )
            ]
        if "polyline" in prompt_lower:
            return [
                ToolCall(
                    name="add_polyline",
                    arguments={"points": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]], "tag": "pline"},
                )
            ]
        if "circle" in prompt_lower:
            return [ToolCall(name="add_circle", arguments={"center_x": 0.0, "center_y": 0.0, "radius": 1.0, "tag": "circle"} )]
        if "line" in prompt_lower or "sketch" in prompt_lower or "image" in prompt_lower:
            return [
                ToolCall(
                    name="add_line",
                    arguments={"start_x": 0.0, "start_y": 0.0, "end_x": 2.0, "end_y": 0.0, "tag": "base"},
                )
            ]
        if "constraint" in prompt_lower:
            return [ToolCall(name="add_constraint", arguments={"kind": "horizontal"})]
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


def _load_image_payload(
    image_path: str,
    max_bytes: int = 2 * 1024 * 1024,
    allowed_mimes: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    path = Path(image_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise ValueError(f"Image path not found: {image_path}")

    size = path.stat().st_size
    if size > max_bytes:
        raise ValueError(f"Image too large ({size} bytes), limit is {max_bytes} bytes")

    mime, _ = mimetypes.guess_type(str(path))
    if not mime:
        mime = "application/octet-stream"
    if allowed_mimes and mime not in allowed_mimes:
        allowed_list = ", ".join(allowed_mimes)
        raise ValueError(f"Unsupported image type {mime}. Use {allowed_list} or set a Vision Upload Command.")

    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return {
        "filename": path.name,
        "mime": mime,
        "bytes": size,
        "data_base64": encoded,
    }


def _is_url(value: str) -> bool:
    lowered = value.lower()
    return lowered.startswith("http://") or lowered.startswith("https://")


def _payload_to_data_url(payload: Optional[Dict[str, Any]]) -> str:
    if not payload:
        return ""
    mime = payload.get("mime") or "application/octet-stream"
    data = payload.get("data_base64") or ""
    return f"data:{mime};base64,{data}"


def _supports_data_url(model_name: Optional[str]) -> bool:
    if not model_name:
        return False
    return model_name in {
        "grok-4-1-fast-reasoning",
        "grok-4-1-fast",
    }


def _should_retry_with_upload(exc: Exception) -> bool:
    text = str(exc).lower()
    if "decode image buffer" in text:
        return True
    if "image_url must either be a base64-encoded image" in text:
        return True
    return False


def _run_upload_command(command: str, image_path: str, timeout: Optional[int]) -> str:
    path = Path(image_path).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"Image path not found: {image_path}")

    cmd = command.replace("{path}", str(path)).replace("{abs_path}", str(path))
    args = shlex.split(cmd)
    if not args:
        return ""

    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout or 30,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        detail = detail.replace("\n", " ")[:200]
        raise ValueError(f"Upload command failed: {detail or 'unknown error'}")

    output = (result.stdout or result.stderr or "").strip()
    match = re.search(r"https?://\S+", output)
    if not match:
        raise ValueError("Upload command did not return a URL")
    return match.group(0)


def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        raise RuntimeError("Async loop already running; use async integration")

    return asyncio.run(coro)
