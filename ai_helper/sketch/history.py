from __future__ import annotations

import json
from typing import Dict, List, Tuple

import bpy
import bmesh
from mathutils import Vector

from .circles import load_circles, save_circles
from .constraints import constraint_from_dict, constraints_to_dict, SketchConstraint
from .store import load_constraints, save_constraints
from .rectangles import load_rectangles, save_rectangles
from .tags import load_tags, save_tags


_HISTORY_KEY = "ai_helper_history"
_MAX_HISTORY = 20


def load_history(obj) -> List[Dict[str, object]]:
    raw = obj.get(_HISTORY_KEY)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [entry for entry in data if isinstance(entry, dict)]


def save_history(obj, history: List[Dict[str, object]]) -> None:
    obj[_HISTORY_KEY] = json.dumps(history)


def snapshot_state(obj, label: str) -> Dict[str, object]:
    verts = [[v.co.x, v.co.y, v.co.z] for v in obj.data.vertices]
    edges = [[e.vertices[0], e.vertices[1]] for e in obj.data.edges]
    constraints = constraints_to_dict(load_constraints(obj))
    circles = load_circles(obj)
    rectangles = load_rectangles(obj)
    tags = load_tags(obj)
    entry = {
        "label": label,
        "verts": verts,
        "edges": edges,
        "constraints": constraints,
        "circles": circles,
        "rectangles": rectangles,
        "tags": tags,
    }

    history = load_history(obj)
    history.append(entry)
    if len(history) > _MAX_HISTORY:
        history = history[-_MAX_HISTORY:]
    save_history(obj, history)
    return entry


def restore_snapshot(obj, snapshot: Dict[str, object]) -> List[SketchConstraint]:
    verts = snapshot.get("verts", [])
    edges = snapshot.get("edges", [])
    constraints = snapshot.get("constraints", [])
    circles = snapshot.get("circles", [])
    rectangles = snapshot.get("rectangles", [])
    tags = snapshot.get("tags", {})

    _replace_mesh(obj, verts, edges)

    restored_constraints: List[SketchConstraint] = []
    if isinstance(constraints, list):
        for item in constraints:
            try:
                restored_constraints.append(constraint_from_dict(item))
            except ValueError:
                continue
    save_constraints(obj, restored_constraints)

    if isinstance(circles, list):
        save_circles(obj, circles)
    if isinstance(rectangles, list):
        save_rectangles(obj, rectangles)
    if isinstance(tags, dict):
        save_tags(obj, tags)

    return restored_constraints


def _replace_mesh(obj, verts: List[List[float]], edges: List[List[int]]) -> None:
    mesh = bpy.data.meshes.new("AI_Sketch")
    bm = bmesh.new()
    for co in verts:
        if len(co) < 3:
            continue
        bm.verts.new(Vector((co[0], co[1], co[2])))
    bm.verts.ensure_lookup_table()
    for pair in edges:
        if len(pair) < 2:
            continue
        i, j = int(pair[0]), int(pair[1])
        if i < 0 or j < 0 or i >= len(bm.verts) or j >= len(bm.verts):
            continue
        bm.edges.new((bm.verts[i], bm.verts[j]))
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    old_mesh = obj.data
    obj.data = mesh
    if old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)
