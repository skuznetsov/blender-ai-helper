from __future__ import annotations

from typing import Any, Dict, List

try:
    import bpy  # type: ignore
    _IN_BLENDER = True
except ModuleNotFoundError:
    _IN_BLENDER = False


def dispatch_tool_calls(tool_calls: List[Dict[str, Any]], context, preview: bool = False) -> Dict[str, List[str]]:
    if not _IN_BLENDER:
        raise RuntimeError("Blender bpy module not available")

    messages: List[str] = []
    errors: List[str] = []

    if not preview:
        bpy.ops.ed.undo_push(message="AI Helper LLM Apply")

    for call in tool_calls:
        name = call.get("name")
        args = call.get("arguments", {})
        handler = _HANDLERS.get(name)
        if handler is None:
            errors.append(f"Unsupported tool: {name}")
            continue

        try:
            handler(context, args, preview, messages)
        except Exception as exc:
            errors.append(f"{name} failed: {exc}")

    return {"messages": messages, "errors": errors}


def _get_object(context, name: str):
    return context.scene.objects.get(name)


def _transform_object(context, args: Dict[str, Any], preview: bool, messages: List[str]) -> None:
    name = args.get("name")
    if not name:
        raise ValueError("Missing object name")

    obj = _get_object(context, name)
    if obj is None:
        raise ValueError(f"Object not found: {name}")

    loc = args.get("location")
    rot = args.get("rotation")
    scale = args.get("scale")

    messages.append(f"transform_object {name}")
    if preview:
        return

    if loc is not None:
        obj.location = loc
    if rot is not None:
        obj.rotation_euler = rot
    if scale is not None:
        obj.scale = scale


def _rename_object(_context, args: Dict[str, Any], preview: bool, messages: List[str]) -> None:
    src = args.get("name")
    dst = args.get("new_name")
    if not src or not dst:
        raise ValueError("Missing name or new_name")

    messages.append(f"rename_object {src} -> {dst}")
    if preview:
        return

    obj = bpy.data.objects.get(src)
    if obj is None:
        raise ValueError(f"Object not found: {src}")
    obj.name = dst


def _duplicate_object(context, args: Dict[str, Any], preview: bool, messages: List[str]) -> None:
    name = args.get("name")
    if not name:
        raise ValueError("Missing object name")

    obj = _get_object(context, name)
    if obj is None:
        raise ValueError(f"Object not found: {name}")

    messages.append(f"duplicate_object {name}")
    if preview:
        return

    new_obj = obj.copy()
    if obj.data:
        new_obj.data = obj.data.copy()
    context.collection.objects.link(new_obj)


def _delete_object(context, args: Dict[str, Any], preview: bool, messages: List[str]) -> None:
    name = args.get("name")
    if not name:
        raise ValueError("Missing object name")

    obj = _get_object(context, name)
    if obj is None:
        raise ValueError(f"Object not found: {name}")

    messages.append(f"delete_object {name}")
    if preview:
        return

    bpy.data.objects.remove(obj, do_unlink=True)


def _add_cube(_context, args: Dict[str, Any], preview: bool, messages: List[str]) -> None:
    size = float(args.get("size", 1.0))
    location = args.get("location", [0.0, 0.0, 0.0])

    messages.append(f"add_cube size={size}")
    if preview:
        return

    bpy.ops.mesh.primitive_cube_add(size=size, location=location)


def _add_constraint(_context, args: Dict[str, Any], preview: bool, messages: List[str]) -> None:
    kind = str(args.get("kind", "")).lower()
    if not kind:
        raise ValueError("Missing constraint kind")

    messages.append(f"add_constraint {kind}")
    if preview:
        return

    if kind == "distance":
        bpy.ops.aihelper.add_distance_constraint(distance=float(args.get("distance", 0.0)))
    elif kind == "angle":
        bpy.ops.aihelper.add_angle_constraint(degrees=float(args.get("degrees", 90.0)))
    elif kind == "radius":
        bpy.ops.aihelper.add_radius_constraint(radius=float(args.get("radius", 0.0)))
    elif kind == "horizontal":
        bpy.ops.aihelper.add_horizontal_constraint()
    elif kind == "vertical":
        bpy.ops.aihelper.add_vertical_constraint()
    elif kind == "coincident":
        bpy.ops.aihelper.add_coincident_constraint()
    elif kind == "midpoint":
        bpy.ops.aihelper.add_midpoint_constraint()
    elif kind == "equal_length":
        bpy.ops.aihelper.add_equal_length_constraint()
    elif kind == "concentric":
        bpy.ops.aihelper.add_concentric_constraint()
    elif kind == "symmetry":
        bpy.ops.aihelper.add_symmetry_constraint()
    elif kind == "tangent":
        bpy.ops.aihelper.add_tangent_constraint()
    elif kind == "parallel":
        bpy.ops.aihelper.add_parallel_constraint()
    elif kind == "perpendicular":
        bpy.ops.aihelper.add_perpendicular_constraint()
    elif kind == "fix":
        bpy.ops.aihelper.add_fix_constraint()
    else:
        raise ValueError(f"Unsupported constraint kind: {kind}")


def _solve_constraints(_context, _args: Dict[str, Any], preview: bool, messages: List[str]) -> None:
    messages.append("solve_constraints")
    if preview:
        return
    bpy.ops.aihelper.solve_constraints()


_HANDLERS = {
    "transform_object": _transform_object,
    "rename_object": _rename_object,
    "duplicate_object": _duplicate_object,
    "delete_object": _delete_object,
    "add_cube": _add_cube,
    "add_constraint": _add_constraint,
    "solve_constraints": _solve_constraints,
}
