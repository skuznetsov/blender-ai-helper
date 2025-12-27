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


_HANDLERS = {
    "transform_object": _transform_object,
    "rename_object": _rename_object,
    "duplicate_object": _duplicate_object,
    "delete_object": _delete_object,
    "add_cube": _add_cube,
}
