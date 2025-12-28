from __future__ import annotations

from typing import Any, Dict, List

from ..sketch.circles import load_circles
from ..sketch.tags import load_tags

try:
    import bpy  # type: ignore
    _IN_BLENDER = True
except ModuleNotFoundError:
    _IN_BLENDER = False


def serialize_selection(context) -> Dict[str, Any]:
    if not _IN_BLENDER:
        return {"error": "bpy unavailable", "objects": []}

    scene = context.scene
    units = scene.unit_settings
    active = context.view_layer.objects.active

    objects: List[Dict[str, Any]] = []
    for obj in context.selected_objects:
        data = {
            "name": obj.name,
            "type": obj.type,
            "location": list(obj.location),
            "rotation": list(obj.rotation_euler),
            "scale": list(obj.scale),
            "dimensions": list(obj.dimensions),
        }

        if obj.type == "MESH" and obj.data:
            data["mesh_counts"] = {
                "verts": len(obj.data.vertices),
                "edges": len(obj.data.edges),
                "faces": len(obj.data.polygons),
            }
            if obj.name == "AI_Sketch":
                data["selection"] = {
                    "verts": [v.index for v in obj.data.vertices if v.select],
                    "edges": [e.index for e in obj.data.edges if e.select],
                }
                data["sketch"] = _sketch_summary(obj)

        objects.append(data)

    return {
        "units": {
            "system": units.system,
            "scale_length": units.scale_length,
        },
        "active_object": active.name if active else None,
        "objects": objects,
    }


def _sketch_summary(obj, max_verts: int = 40, max_edges: int = 40, max_circles: int = 20, max_tags: int = 30):
    verts = obj.data.vertices
    edges = obj.data.edges

    bounds = None
    if verts:
        xs = [v.co.x for v in verts]
        ys = [v.co.y for v in verts]
        bounds = {
            "min": [min(xs), min(ys)],
            "max": [max(xs), max(ys)],
        }

    verts_sample = [
        {"index": v.index, "co": [round(v.co.x, 4), round(v.co.y, 4)]}
        for v in list(verts)[:max_verts]
    ]
    edges_sample = [
        {"index": e.index, "verts": [int(e.vertices[0]), int(e.vertices[1])]}
        for e in list(edges)[:max_edges]
    ]

    circles = []
    for circle in load_circles(obj)[:max_circles]:
        center_id = circle.get("center")
        center_xy = None
        if center_id is not None:
            try:
                center = verts[int(center_id)].co
                center_xy = [round(center.x, 4), round(center.y, 4)]
            except (ValueError, IndexError):
                center_xy = None
        entry = {
            "id": circle.get("id"),
            "center": center_id,
            "center_xy": center_xy,
            "radius": circle.get("radius"),
        }
        if circle.get("is_arc"):
            entry["is_arc"] = True
            entry["start_angle"] = circle.get("start_angle")
            entry["end_angle"] = circle.get("end_angle")
            entry["clockwise"] = circle.get("clockwise")
        circles.append(entry)

    tag_map = load_tags(obj)
    tag_items = list(tag_map.items())[:max_tags]
    tags = {key: value for key, value in tag_items}

    return {
        "bounds": bounds,
        "verts_sample": verts_sample,
        "edges_sample": edges_sample,
        "circles": circles,
        "tags": tags,
    }
