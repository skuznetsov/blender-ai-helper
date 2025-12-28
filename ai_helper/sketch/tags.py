from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Tuple

_TAGS_KEY = "ai_helper_llm_tags"


def load_tags(obj) -> Dict[str, Dict[str, Any]]:
    raw = obj.get(_TAGS_KEY)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}

    tags: Dict[str, Dict[str, Any]] = {}
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        tags[key] = _normalize_entry(value)
    return tags


def save_tags(obj, tags: Dict[str, Dict[str, Any]]) -> None:
    obj[_TAGS_KEY] = json.dumps(tags)


def clear_tags(obj) -> None:
    if _TAGS_KEY in obj:
        del obj[_TAGS_KEY]


def register_tag(
    obj,
    tag: str,
    *,
    verts: Iterable[int] | None = None,
    edges: Iterable[int] | None = None,
    circle_id: str | None = None,
    center: int | None = None,
) -> Dict[str, Any]:
    if not tag:
        return {}

    tags = load_tags(obj)
    entry = tags.get(tag, {})
    entry = _normalize_entry(entry)

    if verts:
        entry["verts"] = _merge_ids(entry.get("verts", []), verts)
    if edges:
        entry["edges"] = _merge_ids(entry.get("edges", []), edges)
    if circle_id:
        entry["circle_id"] = str(circle_id)
    if center is not None:
        entry["center"] = int(center)

    tags[tag] = entry
    save_tags(obj, tags)
    return entry


def resolve_tags(
    obj,
    tags: Iterable[str],
    *,
    prefer_center: bool = True,
) -> Tuple[List[int], List[int]]:
    tag_map = load_tags(obj)
    verts: List[int] = []
    edges: List[int] = []

    for tag in tags:
        entry = tag_map.get(tag)
        if not isinstance(entry, dict):
            continue
        entry = _normalize_entry(entry)
        edges.extend(int(e) for e in entry.get("edges", []))
        if prefer_center and "center" in entry:
            verts.append(int(entry["center"]))
        elif not entry.get("edges"):
            verts.extend(int(v) for v in entry.get("verts", []))

    return _dedupe(verts), _dedupe(edges)


def _normalize_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    if "verts" in entry and isinstance(entry["verts"], list):
        normalized["verts"] = _dedupe(int(v) for v in entry["verts"])
    if "edges" in entry and isinstance(entry["edges"], list):
        normalized["edges"] = _dedupe(int(e) for e in entry["edges"])
    if "circle_id" in entry:
        normalized["circle_id"] = str(entry["circle_id"])
    if "center" in entry:
        try:
            normalized["center"] = int(entry["center"])
        except (TypeError, ValueError):
            pass
    return normalized


def _merge_ids(existing: Iterable[int], extra: Iterable[int]) -> List[int]:
    merged = list(existing) + list(extra)
    return _dedupe(merged)


def _dedupe(items: Iterable[int]) -> List[int]:
    seen = set()
    ordered: List[int] = []
    for item in items:
        try:
            value = int(item)
        except (TypeError, ValueError):
            continue
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered
