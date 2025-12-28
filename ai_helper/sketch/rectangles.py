from __future__ import annotations

import json
import uuid
from typing import Dict, List, Optional

_RECTANGLES_KEY = "ai_helper_rectangles"


def new_rectangle_id() -> str:
    return uuid.uuid4().hex


def load_rectangles(obj) -> List[Dict[str, object]]:
    raw = obj.get(_RECTANGLES_KEY)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []

    rectangles: List[Dict[str, object]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        if "id" not in item or "verts" not in item:
            continue
        rect = {
            "id": str(item.get("id")),
            "center": list(item.get("center", [0.0, 0.0])),
            "width": float(item.get("width", 0.0)),
            "height": float(item.get("height", 0.0)),
            "rotation": float(item.get("rotation", 0.0)),
            "verts": [str(v) for v in item.get("verts", [])],
            "edges": [str(e) for e in item.get("edges", [])],
        }
        if "tag" in item:
            rect["tag"] = str(item.get("tag"))
        rectangles.append(rect)
    return rectangles


def save_rectangles(obj, rectangles: List[Dict[str, object]]) -> None:
    obj[_RECTANGLES_KEY] = json.dumps(rectangles)


def append_rectangle(obj, rectangle: Dict[str, object]) -> None:
    rectangles = load_rectangles(obj)
    rectangles.append(rectangle)
    save_rectangles(obj, rectangles)


def clear_rectangles(obj) -> None:
    if _RECTANGLES_KEY in obj:
        del obj[_RECTANGLES_KEY]


def update_rectangle(obj, rect_id: str, updater) -> bool:
    rectangles = load_rectangles(obj)
    updated = False
    for idx, rect in enumerate(rectangles):
        if rect.get("id") == rect_id:
            rectangles[idx] = updater(rect)
            updated = True
            break
    if updated:
        save_rectangles(obj, rectangles)
    return updated


def find_rectangle_by_tag(rectangles: List[Dict[str, object]], tag: str) -> Optional[Dict[str, object]]:
    for rect in rectangles:
        if rect.get("tag") == tag:
            return rect
    return None
