from __future__ import annotations

import math
from typing import Any, Dict, List

try:
    import bpy  # type: ignore
    import bmesh  # type: ignore
    from mathutils import Vector  # type: ignore
    _IN_BLENDER = True
except ModuleNotFoundError:
    _IN_BLENDER = False

if _IN_BLENDER:
    from ..ops.sketch import (
        add_arc_to_sketch,
        add_circle_to_sketch,
        add_line_to_sketch,
        add_polyline_to_sketch,
        add_rectangle_to_sketch,
        clear_sketch_data,
    )
    from ..sketch.circles import load_circles
    from ..sketch.rectangles import find_rectangle_by_tag, load_rectangles
    from ..sketch.tags import resolve_tags


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


def _set_selection(obj, verts=None, edges=None, extend=False):
    verts = verts or []
    edges = edges or []

    if obj.mode == "EDIT":
        bm = bmesh.from_edit_mesh(obj.data)
        if not extend:
            for v in bm.verts:
                v.select = False
            for e in bm.edges:
                e.select = False
        for vid in verts:
            if 0 <= vid < len(bm.verts):
                bm.verts[vid].select = True
        for eid in edges:
            if 0 <= eid < len(bm.edges):
                bm.edges[eid].select = True
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        return

    if not extend:
        for v in obj.data.vertices:
            v.select = False
        for e in obj.data.edges:
            e.select = False
    for vid in verts:
        if 0 <= vid < len(obj.data.vertices):
            obj.data.vertices[vid].select = True
    for eid in edges:
        if 0 <= eid < len(obj.data.edges):
            obj.data.edges[eid].select = True
    obj.data.update()


def _coerce_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _arg_float(args: Dict[str, Any], key: str):
    if key not in args:
        return None
    return _coerce_float(args.get(key))


def _arg_bool(args: Dict[str, Any], key: str):
    if key not in args:
        return None
    return bool(args.get(key))


def _parse_point(item):
    if isinstance(item, (list, tuple)) and len(item) >= 2:
        x = _coerce_float(item[0])
        y = _coerce_float(item[1])
        if x is None or y is None:
            return None
        return Vector((x, y, 0.0))
    if isinstance(item, dict):
        x = _coerce_float(item.get("x"))
        y = _coerce_float(item.get("y"))
        if x is None or y is None:
            return None
        return Vector((x, y, 0.0))
    return None


def _selected_arc(obj):
    circles = load_circles(obj)
    if not circles:
        return None

    for vert in obj.data.vertices:
        if not vert.select:
            continue
        vid = str(vert.index)
        for circle in circles:
            if not circle.get("is_arc"):
                continue
            if vid == circle.get("center") or vid in circle.get("verts", []):
                return circle

    for edge in obj.data.edges:
        if not edge.select:
            continue
        for vid in edge.vertices:
            vid_str = str(vid)
            for circle in circles:
                if not circle.get("is_arc"):
                    continue
                if vid_str in circle.get("verts", []):
                    return circle
    return None


def _arc_angles_for_circle(obj, circle):
    center_id = circle.get("center")
    if center_id is None:
        return None
    try:
        center = obj.data.vertices[int(center_id)].co
    except (ValueError, IndexError):
        return None
    vert_ids = [int(v) for v in circle.get("verts", [])]
    if len(vert_ids) < 2:
        return None
    try:
        start = obj.data.vertices[vert_ids[0]].co
        end = obj.data.vertices[vert_ids[-1]].co
    except (ValueError, IndexError):
        return None

    def _angle_deg(point):
        return (math.degrees(math.atan2(point.y - center.y, point.x - center.x)) + 360.0) % 360.0

    return _angle_deg(start), _angle_deg(end)


def _find_arc_by_tags(obj, tags):
    circles = load_circles(obj)
    if not circles:
        return None
    verts, edges = resolve_tags(obj, tags, prefer_center=True)
    vert_set = set(int(v) for v in verts)
    edge_set = set(int(e) for e in edges)
    for circle in circles:
        if not circle.get("is_arc"):
            continue
        circle_verts = set(int(v) for v in circle.get("verts", []))
        center_id = circle.get("center")
        if center_id is not None:
            try:
                if int(center_id) in vert_set:
                    return circle
            except ValueError:
                pass
        if circle_verts & vert_set:
            return circle
        if edge_set:
            for eid in edge_set:
                if 0 <= eid < len(obj.data.edges):
                    edge = obj.data.edges[eid]
                    if set(edge.vertices) & circle_verts:
                        return circle
    return None


def _select_arc_geometry(obj, circle, extend=False):
    if not circle:
        return
    verts = []
    edges = []
    for vid in circle.get("verts", []):
        try:
            verts.append(int(vid))
        except (TypeError, ValueError):
            continue
    center_id = circle.get("center")
    if center_id is not None:
        try:
            verts.append(int(center_id))
        except (TypeError, ValueError):
            pass
    circle_edges = set(verts)
    for edge in obj.data.edges:
        if edge.vertices[0] in circle_edges or edge.vertices[1] in circle_edges:
            edges.append(edge.index)
    _set_selection(obj, verts=verts, edges=edges, extend=extend)


def _selected_rectangle(obj):
    rectangles = load_rectangles(obj)
    if not rectangles:
        return None
    selected_verts = {v.index for v in obj.data.vertices if v.select}
    selected_edges = {e.index for e in obj.data.edges if e.select}
    for rect in rectangles:
        rect_verts = {int(v) for v in rect.get("verts", [])}
        rect_edges = {int(e) for e in rect.get("edges", [])}
        if rect_verts & selected_verts or rect_edges & selected_edges:
            return rect
    return None


def _find_rectangle_by_tags(obj, tags):
    rectangles = load_rectangles(obj)
    if not rectangles:
        return None
    for tag in tags:
        rect = find_rectangle_by_tag(rectangles, tag)
        if rect:
            return rect
    return None


def _select_rectangle_geometry(obj, rect, extend=False):
    verts = []
    edges = []
    for vid in rect.get("verts", []):
        try:
            verts.append(int(vid))
        except (TypeError, ValueError):
            continue
    for eid in rect.get("edges", []):
        try:
            edges.append(int(eid))
        except (TypeError, ValueError):
            continue
    _set_selection(obj, verts=verts, edges=edges, extend=extend)


def _add_cube(_context, args: Dict[str, Any], preview: bool, messages: List[str]) -> None:
    size = float(args.get("size", 1.0))
    location = args.get("location", [0.0, 0.0, 0.0])

    messages.append(f"add_cube size={size}")
    if preview:
        return

    bpy.ops.mesh.primitive_cube_add(size=size, location=location)


def _clear_sketch(context, _args: Dict[str, Any], preview: bool, messages: List[str]) -> None:
    messages.append("clear_sketch")
    if preview:
        return

    if not clear_sketch_data(context):
        raise ValueError("No sketch mesh found")


def _add_line(context, args: Dict[str, Any], preview: bool, messages: List[str]) -> None:
    start_x = float(args.get("start_x", 0.0))
    start_y = float(args.get("start_y", 0.0))
    end_x = float(args.get("end_x", 0.0))
    end_y = float(args.get("end_y", 0.0))
    tag = args.get("tag")
    auto_constraints = bool(args.get("auto_constraints", True))

    messages.append(f"add_line ({start_x:g}, {start_y:g}) -> ({end_x:g}, {end_y:g})")
    if preview:
        return

    hv_tolerance = getattr(context.scene.ai_helper, "hv_tolerance_deg", 8.0)
    result = add_line_to_sketch(
        context,
        Vector((start_x, start_y, 0.0)),
        Vector((end_x, end_y, 0.0)),
        tag=tag,
        auto_constraints=auto_constraints,
        hv_tolerance_deg=hv_tolerance,
    )
    if result is None:
        raise ValueError("Unable to add line")


def _add_circle(context, args: Dict[str, Any], preview: bool, messages: List[str]) -> None:
    center_x = float(args.get("center_x", 0.0))
    center_y = float(args.get("center_y", 0.0))
    radius = float(args.get("radius", 1.0))
    segments = int(args.get("segments", 32))
    tag = args.get("tag")

    messages.append(f"add_circle center=({center_x:g}, {center_y:g}) r={radius:g}")
    if preview:
        return

    result = add_circle_to_sketch(
        context,
        Vector((center_x, center_y, 0.0)),
        radius,
        segments=segments,
        tag=tag,
    )
    if result is None:
        raise ValueError("Unable to add circle")


def _add_arc(context, args: Dict[str, Any], preview: bool, messages: List[str]) -> None:
    center_x = float(args.get("center_x", 0.0))
    center_y = float(args.get("center_y", 0.0))
    radius = float(args.get("radius", 1.0))
    start_angle = float(args.get("start_angle", 0.0))
    end_angle = float(args.get("end_angle", 90.0))
    segments = int(args.get("segments", 16))
    clockwise = bool(args.get("clockwise", False))
    tag = args.get("tag")

    messages.append(
        f"add_arc center=({center_x:g}, {center_y:g}) r={radius:g} start={start_angle:g} end={end_angle:g}"
    )
    if preview:
        return

    result = add_arc_to_sketch(
        context,
        Vector((center_x, center_y, 0.0)),
        radius,
        start_angle,
        end_angle,
        segments=segments,
        clockwise=clockwise,
        tag=tag,
    )
    if result is None:
        raise ValueError("Unable to add arc")


def _edit_arc(context, args: Dict[str, Any], preview: bool, messages: List[str]) -> None:
    obj = context.scene.objects.get("AI_Sketch")
    if obj is None or obj.type != "MESH":
        raise ValueError("No sketch mesh found")

    tags = []
    tag = args.get("tag")
    if tag:
        tags.append(str(tag))
    for item in args.get("tags", []) if isinstance(args.get("tags"), list) else []:
        if item:
            tags.append(str(item))

    circle = _find_arc_by_tags(obj, tags) if tags else _selected_arc(obj)
    if not circle:
        raise ValueError("Arc not found")

    if tags:
        _select_arc_geometry(obj, circle, extend=False)
    context.view_layer.objects.active = obj

    radius = _arg_float(args, "radius")
    center_x = _arg_float(args, "center_x")
    center_y = _arg_float(args, "center_y")
    start_angle = _arg_float(args, "start_angle")
    end_angle = _arg_float(args, "end_angle")
    clockwise = _arg_bool(args, "clockwise")

    center_id = circle.get("center")
    if center_id is None:
        raise ValueError("Arc center missing")
    try:
        center = obj.data.vertices[int(center_id)].co
    except (ValueError, IndexError):
        raise ValueError("Arc center invalid")

    if radius is None:
        radius = float(circle.get("radius", 1.0))
    if center_x is None:
        center_x = center.x
    if center_y is None:
        center_y = center.y
    if start_angle is None or end_angle is None:
        stored_start = circle.get("start_angle")
        stored_end = circle.get("end_angle")
        if start_angle is None and stored_start is not None:
            start_angle = float(stored_start)
        if end_angle is None and stored_end is not None:
            end_angle = float(stored_end)
    if start_angle is None or end_angle is None:
        angles = _arc_angles_for_circle(obj, circle)
        if angles:
            if start_angle is None:
                start_angle = angles[0]
            if end_angle is None:
                end_angle = angles[1]
    if start_angle is None or end_angle is None:
        raise ValueError("Arc angles missing")
    if clockwise is None:
        clockwise = bool(circle.get("clockwise", False))

    messages.append(
        f"edit_arc center=({center_x:g}, {center_y:g}) r={radius:g} start={start_angle:g} end={end_angle:g}"
    )
    if preview:
        return

    result = bpy.ops.aihelper.edit_arc(
        radius=radius,
        center_x=center_x,
        center_y=center_y,
        start_angle=start_angle,
        end_angle=end_angle,
        clockwise=clockwise,
    )
    if "FINISHED" not in result:
        raise ValueError("edit_arc operator failed")


def _edit_rectangle(context, args: Dict[str, Any], preview: bool, messages: List[str]) -> None:
    obj = context.scene.objects.get("AI_Sketch")
    if obj is None or obj.type != "MESH":
        raise ValueError("No sketch mesh found")

    tags = []
    tag = args.get("tag")
    if tag:
        tags.append(str(tag))
    for item in args.get("tags", []) if isinstance(args.get("tags"), list) else []:
        if item:
            tags.append(str(item))

    rect = _find_rectangle_by_tags(obj, tags) if tags else _selected_rectangle(obj)
    if not rect:
        raise ValueError("Rectangle not found")

    if tags:
        _select_rectangle_geometry(obj, rect, extend=False)
    context.view_layer.objects.active = obj

    width = _arg_float(args, "width")
    height = _arg_float(args, "height")
    center_x = _arg_float(args, "center_x")
    center_y = _arg_float(args, "center_y")
    rotation_deg = _arg_float(args, "rotation_deg")

    if width is None:
        width = float(rect.get("width", 1.0))
    if height is None:
        height = float(rect.get("height", 1.0))
    if center_x is None or center_y is None:
        center = rect.get("center", [0.0, 0.0])
        if center_x is None:
            center_x = float(center[0]) if isinstance(center, list) and len(center) >= 2 else 0.0
        if center_y is None:
            center_y = float(center[1]) if isinstance(center, list) and len(center) >= 2 else 0.0
    if rotation_deg is None:
        rotation_deg = float(rect.get("rotation", 0.0))

    messages.append(
        f"edit_rectangle center=({center_x:g}, {center_y:g}) w={width:g} h={height:g} rot={rotation_deg:g}"
    )
    if preview:
        return

    result = bpy.ops.aihelper.edit_rectangle(
        width=width,
        height=height,
        center_x=center_x,
        center_y=center_y,
        rotation_deg=rotation_deg,
    )
    if "FINISHED" not in result:
        raise ValueError("edit_rectangle operator failed")


def _add_polyline(context, args: Dict[str, Any], preview: bool, messages: List[str]) -> None:
    raw_points = args.get("points", [])
    points = []
    if isinstance(raw_points, list):
        for item in raw_points:
            point = _parse_point(item)
            if point is not None:
                points.append(point)

    closed = bool(args.get("closed", False))
    tag = args.get("tag")
    auto_constraints = bool(args.get("auto_constraints", True))

    messages.append(f"add_polyline points={len(points)} closed={closed}")
    if preview:
        return

    hv_tolerance = getattr(context.scene.ai_helper, "hv_tolerance_deg", 8.0)
    result = add_polyline_to_sketch(
        context,
        points,
        closed=closed,
        tag=tag,
        auto_constraints=auto_constraints,
        hv_tolerance_deg=hv_tolerance,
    )
    if result is None:
        raise ValueError("Unable to add polyline")


def _add_rectangle(context, args: Dict[str, Any], preview: bool, messages: List[str]) -> None:
    center_x = float(args.get("center_x", 0.0))
    center_y = float(args.get("center_y", 0.0))
    width = float(args.get("width", 0.0))
    height = float(args.get("height", 0.0))
    rotation_deg = float(args.get("rotation_deg", 0.0))
    tag = args.get("tag")
    auto_constraints = bool(args.get("auto_constraints", True))

    messages.append(
        f"add_rectangle center=({center_x:g}, {center_y:g}) w={width:g} h={height:g} rot={rotation_deg:g}"
    )
    if preview:
        return

    hv_tolerance = getattr(context.scene.ai_helper, "hv_tolerance_deg", 8.0)
    result = add_rectangle_to_sketch(
        context,
        Vector((center_x, center_y, 0.0)),
        width,
        height,
        rotation_deg=rotation_deg,
        tag=tag,
        auto_constraints=auto_constraints,
        hv_tolerance_deg=hv_tolerance,
    )
    if result is None:
        raise ValueError("Unable to add rectangle")


def _select_sketch_entities(context, args: Dict[str, Any], preview: bool, messages: List[str]) -> None:
    obj = context.scene.objects.get("AI_Sketch")
    if obj is None or obj.type != "MESH":
        raise ValueError("No sketch mesh found")

    verts = [int(v) for v in args.get("verts", []) if isinstance(v, (int, float, str))]
    edges = [int(e) for e in args.get("edges", []) if isinstance(e, (int, float, str))]
    tags = [str(t) for t in args.get("tags", []) if t]
    extend = bool(args.get("extend", False))

    if tags:
        tag_verts, tag_edges = resolve_tags(obj, tags, prefer_center=True)
        verts.extend(tag_verts)
        edges.extend(tag_edges)

    messages.append(f"select_sketch_entities verts={len(verts)} edges={len(edges)}")
    if preview:
        return

    _set_selection(obj, verts=verts, edges=edges, extend=extend)
    context.view_layer.objects.active = obj


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


def _loft_profiles(_context, args: Dict[str, Any], preview: bool, messages: List[str]) -> None:
    profile_tags = args.get("profile_tags")
    tags = []
    if isinstance(profile_tags, list):
        tags = [str(tag).strip() for tag in profile_tags if tag]
    elif isinstance(profile_tags, str):
        tags = [tag.strip() for tag in profile_tags.split(",") if tag.strip()]

    offset_z = _coerce_float(args.get("offset_z"), 1.0)

    if tags:
        messages.append(f"loft_profiles tags={len(tags)} offset_z={offset_z:g}")
        if preview:
            return
        result = bpy.ops.aihelper.loft_profiles(profile_tags=", ".join(tags), offset_z=offset_z)
        if "FINISHED" not in result:
            raise ValueError("loft_profiles operator failed")
        return

    tag_a = args.get("profile_a_tag")
    tag_b = args.get("profile_b_tag")
    if not tag_a or not tag_b:
        raise ValueError("Missing profile tags")

    messages.append(f"loft_profiles tags=2 offset_z={offset_z:g}")
    if preview:
        return
    result = bpy.ops.aihelper.loft_profiles(profile_a_tag=str(tag_a), profile_b_tag=str(tag_b), offset_z=offset_z)
    if "FINISHED" not in result:
        raise ValueError("loft_profiles operator failed")


def _sweep_profile(_context, args: Dict[str, Any], preview: bool, messages: List[str]) -> None:
    profile_tag = args.get("profile_tag")
    path_tag = args.get("path_tag")
    if not profile_tag or not path_tag:
        raise ValueError("Missing profile or path tag")

    twist_deg = _coerce_float(args.get("twist_deg"), 0.0)
    messages.append(f"sweep_profile twist={twist_deg:g}")
    if preview:
        return
    result = bpy.ops.aihelper.sweep_profile(
        profile_tag=str(profile_tag),
        path_tag=str(path_tag),
        twist_deg=twist_deg,
    )
    if "FINISHED" not in result:
        raise ValueError("sweep_profile operator failed")


_HANDLERS = {
    "transform_object": _transform_object,
    "rename_object": _rename_object,
    "duplicate_object": _duplicate_object,
    "delete_object": _delete_object,
    "add_cube": _add_cube,
    "clear_sketch": _clear_sketch,
    "add_line": _add_line,
    "add_circle": _add_circle,
    "add_arc": _add_arc,
    "edit_arc": _edit_arc,
    "add_polyline": _add_polyline,
    "add_rectangle": _add_rectangle,
    "edit_rectangle": _edit_rectangle,
    "select_sketch_entities": _select_sketch_entities,
    "add_constraint": _add_constraint,
    "solve_constraints": _solve_constraints,
    "loft_profiles": _loft_profiles,
    "sweep_profile": _sweep_profile,
}
