from __future__ import annotations

import json
import uuid
from typing import Dict, List, Optional


_CIRCLES_KEY = "ai_helper_circles"


def new_circle_id() -> str:
    return uuid.uuid4().hex


def load_circles(obj) -> List[Dict[str, object]]:
    raw = obj.get(_CIRCLES_KEY)
    if not raw:
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []

    circles: List[Dict[str, object]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        if "id" not in item or "center" not in item or "verts" not in item:
            continue
        circles.append(
            {
                "id": str(item["id"]),
                "center": str(item["center"]),
                "verts": [str(v) for v in item.get("verts", [])],
                "radius": float(item.get("radius", 0.0)),
            }
        )
    return circles


def save_circles(obj, circles: List[Dict[str, object]]) -> None:
    obj[_CIRCLES_KEY] = json.dumps(circles)


def append_circle(obj, circle: Dict[str, object]) -> None:
    circles = load_circles(obj)
    circles.append(circle)
    save_circles(obj, circles)


def find_circle(circles: List[Dict[str, object]], circle_id: str) -> Optional[Dict[str, object]]:
    for circle in circles:
        if circle.get("id") == circle_id:
            return circle
    return None


def find_circle_by_center(circles: List[Dict[str, object]], center_id: str) -> Optional[Dict[str, object]]:
    for circle in circles:
        if circle.get("center") == center_id:
            return circle
    return None


def find_circle_by_vertex(circles: List[Dict[str, object]], vertex_id: str) -> Optional[Dict[str, object]]:
    for circle in circles:
        if vertex_id in circle.get("verts", []):
            return circle
    return None


def update_circle_radius(obj, circle_id: str, radius: float) -> bool:
    circles = load_circles(obj)
    updated = False
    for circle in circles:
        if circle.get("id") == circle_id:
            circle["radius"] = float(radius)
            updated = True
            break
    if updated:
        save_circles(obj, circles)
    return updated
