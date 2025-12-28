from __future__ import annotations

from typing import Any, Dict, List

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

        objects.append(data)

    return {
        "units": {
            "system": units.system,
            "scale_length": units.scale_length,
        },
        "active_object": active.name if active else None,
        "objects": objects,
    }
