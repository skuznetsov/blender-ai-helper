import math
import os
import sys
import tempfile
import types
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import ai_helper  # noqa: E402
from ai_helper.llm import GrokAdapter, dispatch_tool_calls  # noqa: E402
from ai_helper.sketch.circles import load_circles  # noqa: E402
from ai_helper.sketch.constraints import AngleConstraint, RadiusConstraint  # noqa: E402
from ai_helper.sketch.history import load_history, restore_snapshot, snapshot_state  # noqa: E402
from ai_helper.sketch.rectangles import load_rectangles  # noqa: E402
from ai_helper.sketch.store import load_constraints  # noqa: E402
from ai_helper.sketch.tags import load_tags, register_tag  # noqa: E402
from ai_helper.ops.constraints import (  # noqa: E402
    _angle_targets,
    _circle_current_radius,
    _distance_targets,
)
from ai_helper.ops.sketch import (  # noqa: E402
    apply_angle_snap,
    apply_axis_lock,
    format_preview,
    parse_input,
    snap_to_features,
    snap_to_grid,
)


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def clear_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)


def new_sketch():
    clear_scene()
    mesh = bpy.data.meshes.new("AI_Sketch")
    obj = bpy.data.objects.new("AI_Sketch", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    return obj


def build_mesh(obj, verts, edges):
    bm = bmesh.new()
    for co in verts:
        bm.verts.new(co)
    bm.verts.ensure_lookup_table()
    for i, j in edges:
        bm.edges.new((bm.verts[i], bm.verts[j]))
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    v_indices = list(range(len(obj.data.vertices)))
    e_indices = list(range(len(obj.data.edges)))
    return v_indices, e_indices


def clear_selection(obj):
    for v in obj.data.vertices:
        v.select = False
    for e in obj.data.edges:
        e.select = False
    obj.data.update()


def select(obj, verts=(), edges=()):
    clear_selection(obj)
    for vid in verts:
        obj.data.vertices[vid].select = True
    for eid in edges:
        obj.data.edges[eid].select = True
    obj.data.update()


def edge_direction(obj, edge_index):
    edge = obj.data.edges[edge_index]
    v1 = obj.data.vertices[edge.vertices[0]].co
    v2 = obj.data.vertices[edge.vertices[1]].co
    vec = v2 - v1
    if vec.length < 1e-8:
        return Vector((1.0, 0.0, 0.0))
    return vec.normalized()


def angle_between(vec1, vec2):
    dot = max(min(vec1.dot(vec2), 1.0), -1.0)
    return math.degrees(math.acos(dot))


def find_dimension_label(constraint_id, kind=None):
    for obj in bpy.data.objects:
        if obj.get("ai_helper_dimension_id") == constraint_id:
            if kind is None or obj.get("ai_helper_dimension_kind") == kind:
                return obj
    return None


def selected_vertex_indices(obj):
    return [v.index for v in obj.data.vertices if v.select]


def assert_vec_close(vec, expected, tol=1e-3):
    check(abs(vec.x - expected[0]) < tol, f"vec.x {vec.x} != {expected[0]}")
    check(abs(vec.y - expected[1]) < tol, f"vec.y {vec.y} != {expected[1]}")


def add_fix(obj, vid):
    select(obj, verts=[vid])
    result = bpy.ops.aihelper.add_fix_constraint()
    check("FINISHED" in result, "add_fix_constraint failed")


def test_precision_vertex_coords():
    obj = new_sketch()
    v_indices, _ = build_mesh(obj, [(0.0, 0.0, 0.0)], [])
    select(obj, verts=[v_indices[0]])
    result = bpy.ops.aihelper.set_vertex_coords(x=1.5, y=-2.0, relative=False)
    check("FINISHED" in result, "set_vertex_coords failed")
    v = obj.data.vertices[v_indices[0]]
    check(abs(v.co.x - 1.5) < 1e-4 and abs(v.co.y + 2.0) < 1e-4, "vertex coords incorrect")


def test_precision_edge_length():
    obj = new_sketch()
    v_indices, e_indices = build_mesh(obj, [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)], [(0, 1)])
    select(obj, edges=[e_indices[0]])
    result = bpy.ops.aihelper.set_edge_length(length=2.0, anchor="START")
    check("FINISHED" in result, "set_edge_length failed")
    v1 = obj.data.vertices[v_indices[0]].co
    v2 = obj.data.vertices[v_indices[1]].co
    check(abs((v2 - v1).length - 2.0) < 1e-4, "edge length incorrect")


def test_precision_edge_angle():
    obj = new_sketch()
    v_indices, e_indices = build_mesh(obj, [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)], [(0, 1)])
    select(obj, edges=[e_indices[0]])
    result = bpy.ops.aihelper.set_edge_angle(angle=90.0, anchor="START")
    check("FINISHED" in result, "set_edge_angle failed")
    v1 = obj.data.vertices[v_indices[0]].co
    v2 = obj.data.vertices[v_indices[1]].co
    angle = math.degrees(math.atan2(v2.y - v1.y, v2.x - v1.x))
    check(abs(angle - 90.0) < 1e-2, "edge angle incorrect")


def test_inspector_vertex():
    obj = new_sketch()
    v_indices, _ = build_mesh(obj, [(0.0, 0.0, 0.0)], [])
    select(obj, verts=[v_indices[0]])
    props = bpy.context.scene.ai_helper
    props.inspector_vertex_x = 2.5
    props.inspector_vertex_y = -1.5
    result = bpy.ops.aihelper.inspector_apply_vertex()
    check("FINISHED" in result, "inspector vertex apply failed")
    v = obj.data.vertices[v_indices[0]]
    check(abs(v.co.x - 2.5) < 1e-4 and abs(v.co.y + 1.5) < 1e-4, "inspector vertex coords incorrect")


def test_inspector_edge():
    obj = new_sketch()
    v_indices, e_indices = build_mesh(obj, [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)], [(0, 1)])
    select(obj, edges=[e_indices[0]])
    props = bpy.context.scene.ai_helper
    props.inspector_edge_length = 3.0
    props.inspector_edge_anchor = "START"
    result = bpy.ops.aihelper.inspector_apply_edge_length()
    check("FINISHED" in result, "inspector edge length apply failed")
    v1 = obj.data.vertices[v_indices[0]].co
    v2 = obj.data.vertices[v_indices[1]].co
    check(abs((v2 - v1).length - 3.0) < 1e-4, "inspector edge length incorrect")

    props.inspector_edge_angle = 90.0
    result = bpy.ops.aihelper.inspector_apply_edge_angle()
    check("FINISHED" in result, "inspector edge angle apply failed")
    v1 = obj.data.vertices[v_indices[0]].co
    v2 = obj.data.vertices[v_indices[1]].co
    angle = math.degrees(math.atan2(v2.y - v1.y, v2.x - v1.x))
    check(abs(angle - 90.0) < 1e-2, "inspector edge angle incorrect")


def test_inspector_arc():
    obj = new_sketch()
    result = bpy.ops.aihelper.add_arc(
        radius=1.0,
        center_x=0.0,
        center_y=0.0,
        start_angle=0.0,
        end_angle=90.0,
        segments=8,
    )
    check("FINISHED" in result, "add_arc operator failed for inspector")
    select(obj, edges=[0])
    props = bpy.context.scene.ai_helper
    props.inspector_arc_radius = 2.0
    props.inspector_arc_center_x = 1.0
    props.inspector_arc_center_y = 0.0
    props.inspector_arc_start_angle = 0.0
    props.inspector_arc_end_angle = 180.0
    result = bpy.ops.aihelper.inspector_apply_arc()
    check("FINISHED" in result, "inspector arc apply failed")
    circles = load_circles(obj)
    check(len(circles) == 1, "inspector arc circle missing")
    circle = circles[0]
    check(abs(circle.get("radius", 0.0) - 2.0) < 1e-4, "inspector arc radius not updated")


def test_inspector_rectangle():
    obj = new_sketch()
    result = bpy.ops.aihelper.add_rectangle(
        width=2.0,
        height=1.0,
        center_x=0.0,
        center_y=0.0,
        rotation_deg=0.0,
    )
    check("FINISHED" in result, "add_rectangle operator failed for inspector")
    rects = load_rectangles(obj)
    check(len(rects) == 1, "inspector rectangle metadata missing")
    rect = rects[0]
    vert_ids = [int(v) for v in rect.get("verts", [])]
    orig_coords = [obj.data.vertices[vid].co.copy() for vid in vert_ids]

    select(obj, edges=[0])
    props = bpy.context.scene.ai_helper
    props.inspector_rect_center_x = 1.0
    props.inspector_rect_center_y = -1.0
    props.inspector_rect_width = 4.0
    props.inspector_rect_height = 2.0
    props.inspector_rect_rotation = 15.0
    result = bpy.ops.aihelper.inspector_apply_rectangle()
    check("FINISHED" in result, "inspector rectangle apply failed")
    rects = load_rectangles(obj)
    check(len(rects) == 1, "inspector rectangle missing")
    rect = rects[0]
    center = rect.get("center", [0.0, 0.0])
    check(abs(center[0] - 1.0) < 1e-3 and abs(center[1] + 1.0) < 1e-3, "inspector rectangle center not applied")
    check(rect.get("width", 0.0) > 0.0 and rect.get("height", 0.0) > 0.0, "inspector rectangle size invalid")
    coords = [obj.data.vertices[vid].co for vid in vert_ids]
    moved = any((coords[idx] - orig_coords[idx]).length > 0.1 for idx in range(len(coords)))
    check(moved, "inspector rectangle vertices did not move")

def test_midpoint_constraint():
    obj = new_sketch()
    v_indices, e_indices = build_mesh(
        obj,
        [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        [(0, 1)],
    )
    add_fix(obj, v_indices[0])
    add_fix(obj, v_indices[1])
    select(obj, edges=[e_indices[0]], verts=[v_indices[2]])
    result = bpy.ops.aihelper.add_midpoint_constraint()
    check("FINISHED" in result, "add_midpoint_constraint failed")
    v1 = obj.data.vertices[v_indices[0]].co
    v2 = obj.data.vertices[v_indices[1]].co
    vm = obj.data.vertices[v_indices[2]].co
    mid = (v1 + v2) * 0.5
    check((vm - mid).length < 1e-3, "midpoint constraint failed")


def test_equal_length_constraint():
    obj = new_sketch()
    v_indices, e_indices = build_mesh(
        obj,
        [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0), (0.0, 3.0, 0.0)],
        [(0, 1), (2, 3)],
    )
    select(obj, edges=[e_indices[0], e_indices[1]])
    result = bpy.ops.aihelper.add_equal_length_constraint()
    check("FINISHED" in result, "add_equal_length_constraint failed")
    e0 = obj.data.edges[e_indices[0]]
    e1 = obj.data.edges[e_indices[1]]
    len0 = (obj.data.vertices[e0.vertices[1]].co - obj.data.vertices[e0.vertices[0]].co).length
    len1 = (obj.data.vertices[e1.vertices[1]].co - obj.data.vertices[e1.vertices[0]].co).length
    check(abs(len0 - len1) < 1e-3, "equal length constraint failed")


def test_coincident_constraint():
    obj = new_sketch()
    v_indices, _ = build_mesh(obj, [(0.0, 0.0, 0.0), (1.5, 1.0, 0.0)], [])
    select(obj, verts=[v_indices[0], v_indices[1]])
    result = bpy.ops.aihelper.add_coincident_constraint()
    check("FINISHED" in result, "add_coincident_constraint failed")
    v1 = obj.data.vertices[v_indices[0]].co
    v2 = obj.data.vertices[v_indices[1]].co
    check((v2 - v1).length < 1e-3, "coincident constraint failed")


def test_parallel_constraint():
    obj = new_sketch()
    v_indices, e_indices = build_mesh(
        obj,
        [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 2.0, 0.0)],
        [(0, 1), (2, 3)],
    )
    add_fix(obj, v_indices[0])
    add_fix(obj, v_indices[1])
    select(obj, edges=[e_indices[0], e_indices[1]])
    result = bpy.ops.aihelper.add_parallel_constraint()
    check("FINISHED" in result, "add_parallel_constraint failed")
    d1 = edge_direction(obj, e_indices[0])
    d2 = edge_direction(obj, e_indices[1])
    dot = abs(d1.dot(d2))
    check(abs(dot - 1.0) < 1e-3, "parallel constraint failed")


def test_perpendicular_constraint():
    obj = new_sketch()
    v_indices, e_indices = build_mesh(
        obj,
        [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 2.0, 0.0)],
        [(0, 1), (2, 3)],
    )
    add_fix(obj, v_indices[0])
    add_fix(obj, v_indices[1])
    select(obj, edges=[e_indices[0], e_indices[1]])
    result = bpy.ops.aihelper.add_perpendicular_constraint()
    check("FINISHED" in result, "add_perpendicular_constraint failed")
    d1 = edge_direction(obj, e_indices[0])
    d2 = edge_direction(obj, e_indices[1])
    dot = abs(d1.dot(d2))
    check(dot < 1e-3, "perpendicular constraint failed")


def test_angle_constraint_edit():
    obj = new_sketch()
    v_indices, e_indices = build_mesh(
        obj,
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)],
        [(0, 1), (1, 2)],
    )
    add_fix(obj, v_indices[0])
    add_fix(obj, v_indices[1])
    select(obj, edges=[e_indices[0], e_indices[1]])
    result = bpy.ops.aihelper.add_angle_constraint(degrees=45.0)
    check("FINISHED" in result, "add_angle_constraint failed")

    constraints = load_constraints(obj)
    angle_constraint = next((c for c in constraints if isinstance(c, AngleConstraint)), None)
    check(angle_constraint is not None, "angle constraint missing")
    label = find_dimension_label(angle_constraint.id, "angle")
    check(label is not None, "angle dimension label missing")

    v0 = obj.data.vertices[v_indices[0]].co
    v1 = obj.data.vertices[v_indices[1]].co
    v2 = obj.data.vertices[v_indices[2]].co
    angle = angle_between(v0 - v1, v2 - v1)
    check(abs(angle - 45.0) < 1e-2, "angle constraint failed")

    result = bpy.ops.aihelper.edit_selected_dimension(
        constraint_id=angle_constraint.id,
        kind="angle",
        degrees=60.0,
    )
    check("FINISHED" in result, "edit_selected_dimension angle failed")
    constraints = load_constraints(obj)
    angle_constraint = next((c for c in constraints if isinstance(c, AngleConstraint)), None)
    check(angle_constraint is not None, "angle constraint missing after edit")
    check(abs(angle_constraint.degrees - 60.0) < 1e-3, "angle constraint not updated")
    v0 = obj.data.vertices[v_indices[0]].co
    v1 = obj.data.vertices[v_indices[1]].co
    v2 = obj.data.vertices[v_indices[2]].co
    angle = angle_between(v0 - v1, v2 - v1)
    check(abs(angle - 60.0) < 1e-1, "angle constraint edit failed")


def test_sketch_input_and_preview():
    start = Vector((1.0, 2.0, 0.0))
    assert_vec_close(parse_input("1,2", start, True), (2.0, 4.0))
    assert_vec_close(parse_input("=3,4", start, True), (3.0, 4.0))
    assert_vec_close(parse_input("@2<90", start, True), (1.0, 4.0))
    check(parse_input("bad", start, True) is None, "invalid input should return None")

    start = Vector((0.0, 0.0, 0.0))
    point = Vector((3.0, 4.0, 0.0))
    preview = format_preview(start, point)
    expected_angle = (math.degrees(math.atan2(4.0, 3.0)) + 360.0) % 360.0
    check(preview.startswith("len=5.000"), "preview length incorrect")
    check(f"ang={expected_angle:.1f}" in preview, "preview angle incorrect")


def test_sketch_snapping():
    snap_radius = 1.0
    grid_step = 1.0
    scale_length = bpy.context.scene.unit_settings.scale_length

    assert_vec_close(
        snap_to_grid(Vector((0.49, 0.49, 0.0)), grid_step, scale_length, True),
        (0.0, 0.0),
    )
    assert_vec_close(
        snap_to_grid(Vector((0.6, 0.6, 0.0)), grid_step, scale_length, True),
        (1.0, 1.0),
    )

    obj = new_sketch()
    build_mesh(obj, [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)], [(0, 1)])
    snapped = snap_to_features(
        Vector((1.8, 0.2, 0.0)),
        obj,
        snap_radius,
        scale_length,
        True,
        False,
        False,
    )
    check(snapped is not None, "vertex snap missing")
    assert_vec_close(snapped, (2.0, 0.0))

    snapped = snap_to_features(
        Vector((1.0, 0.2, 0.0)),
        obj,
        snap_radius,
        scale_length,
        False,
        True,
        False,
    )
    check(snapped is not None, "midpoint snap missing")
    assert_vec_close(snapped, (1.0, 0.0))

    obj = new_sketch()
    build_mesh(
        obj,
        [(-1.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 1.0, 0.0)],
        [(0, 1), (2, 3)],
    )
    snapped = snap_to_features(
        Vector((0.1, 0.1, 0.0)),
        obj,
        snap_radius,
        scale_length,
        False,
        False,
        True,
    )
    check(snapped is not None, "intersection snap missing")
    assert_vec_close(snapped, (0.0, 0.0))


def test_sketch_axis_lock_and_angle_snap():
    start = Vector((1.0, 2.0, 0.0))
    locked = apply_axis_lock(Vector((5.0, 7.0, 0.0)), start, "X")
    assert_vec_close(locked, (5.0, 2.0))
    locked = apply_axis_lock(Vector((5.0, 7.0, 0.0)), start, "Y")
    assert_vec_close(locked, (1.0, 7.0))

    start = Vector((0.0, 0.0, 0.0))
    angle = math.radians(20.0)
    location = Vector((math.cos(angle) * 2.0, math.sin(angle) * 2.0, 0.0))
    snapped = apply_angle_snap(location, start, True, 45.0, None)
    check(abs(snapped.y) < 1e-3, "angle snap failed")

    props = bpy.context.scene.ai_helper
    props.angle_snap_deg = 15.0
    props.angle_snap_enabled = False
    result = bpy.ops.aihelper.set_angle_snap_preset(angle=30.0, enable=True)
    check("FINISHED" in result, "angle snap preset failed")
    check(abs(props.angle_snap_deg - 30.0) < 1e-3, "angle snap preset not set")
    check(props.angle_snap_enabled is True, "angle snap preset did not enable")


def test_constraint_dialog_prefill():
    obj = new_sketch()
    v_indices, e_indices = build_mesh(obj, [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)], [(0, 1)])
    select(obj, edges=[e_indices[0]])
    targets = _distance_targets(obj)
    check(targets is not None, "distance targets missing")
    v1, v2 = targets
    check(abs((v2.co - v1.co).length - 2.0) < 1e-3, "distance prefill incorrect")

    obj = new_sketch()
    v_indices, e_indices = build_mesh(
        obj,
        [(1.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.5, 0.8660254, 0.0)],
        [(0, 1), (1, 2)],
    )
    select(obj, edges=[e_indices[0], e_indices[1]])
    targets = _angle_targets(obj)
    check(targets is not None, "angle targets missing")
    _p1, _vertex, _p2, angle_deg = targets
    check(abs(angle_deg - 60.0) < 1e-1, "angle prefill incorrect")

    obj = new_sketch()
    result = bpy.ops.aihelper.add_circle(radius=1.5, segments=16, center_x=0.0, center_y=0.0)
    check("FINISHED" in result, "add_circle failed for radius prefill")
    circles = load_circles(obj)
    select(obj, verts=[int(circles[0]["verts"][0])])
    radius = _circle_current_radius(obj, circles[0])
    check(radius is not None and abs(radius - 1.5) < 1e-3, "radius prefill incorrect")


def test_symmetry_constraint():
    obj = new_sketch()
    v_indices, e_indices = build_mesh(
        obj,
        [(-1.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 1.0, 0.0), (-0.2, -0.4, 0.0)],
        [(0, 1)],
    )
    add_fix(obj, v_indices[0])
    add_fix(obj, v_indices[1])
    select(obj, edges=[e_indices[0]], verts=[v_indices[2], v_indices[3]])
    result = bpy.ops.aihelper.add_symmetry_constraint()
    check("FINISHED" in result, "add_symmetry_constraint failed")
    p1 = obj.data.vertices[v_indices[2]].co
    p2 = obj.data.vertices[v_indices[3]].co
    check(abs(p1.y + p2.y) < 1e-3, "symmetry constraint failed")


def test_circle_constraints():
    obj = new_sketch()
    result = bpy.ops.aihelper.add_circle(radius=1.0, segments=16, center_x=5.0, center_y=0.0)
    check("FINISHED" in result, "add_circle failed")
    result = bpy.ops.aihelper.add_circle(radius=0.5, segments=16, center_x=7.0, center_y=0.0)
    check("FINISHED" in result, "add_circle failed")
    circles = load_circles(obj)
    check(len(circles) == 2, "circle metadata missing")

    select(obj, verts=[int(circles[0]["verts"][0])])
    result = bpy.ops.aihelper.add_radius_constraint()
    check("FINISHED" in result, "add_radius_constraint failed")

    circles = load_circles(obj)
    select(obj, verts=[int(circles[0]["verts"][1]), int(circles[1]["verts"][1])])
    result = bpy.ops.aihelper.add_concentric_constraint()
    check("FINISHED" in result, "add_concentric_constraint failed")

    center1 = obj.data.vertices[int(circles[0]["center"])].co
    center2 = obj.data.vertices[int(circles[1]["center"])].co
    check((center1 - center2).length < 1e-3, "concentric constraint failed")

    constraints = load_constraints(obj)
    radius_constraint = next((c for c in constraints if isinstance(c, RadiusConstraint)), None)
    check(radius_constraint is not None, "radius constraint missing")
    label = find_dimension_label(radius_constraint.id, "radius")
    check(label is not None, "radius dimension label missing")
    result = bpy.ops.aihelper.edit_selected_dimension(
        constraint_id=radius_constraint.id,
        kind="radius",
        radius=2.0,
    )
    check("FINISHED" in result, "edit_selected_dimension radius failed")
    constraints = load_constraints(obj)
    radius_constraint = next((c for c in constraints if isinstance(c, RadiusConstraint)), None)
    check(radius_constraint is not None, "radius constraint missing after edit")
    check(abs(radius_constraint.radius - 2.0) < 1e-3, "radius constraint not updated")
    center = obj.data.vertices[int(circles[0]["center"])].co
    v = obj.data.vertices[int(circles[0]["verts"][0])].co
    check(abs((v - center).length - 2.0) < 1e-2, "radius edit failed")


def test_tangent_constraint():
    obj = new_sketch()
    v_indices, e_indices = build_mesh(
        obj,
        [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
        [(0, 1)],
    )
    add_fix(obj, v_indices[0])
    add_fix(obj, v_indices[1])
    result = bpy.ops.aihelper.add_circle(radius=1.0, segments=16, center_x=1.0, center_y=2.0)
    check("FINISHED" in result, "add_circle failed")

    circles = load_circles(obj)
    select(obj, edges=[e_indices[0]], verts=[int(circles[0]["verts"][0])])
    result = bpy.ops.aihelper.add_tangent_constraint()
    check("FINISHED" in result, "add_tangent_constraint failed")

    center = obj.data.vertices[int(circles[0]["center"])].co
    v1 = obj.data.vertices[v_indices[0]].co
    v2 = obj.data.vertices[v_indices[1]].co
    line_vec = v2 - v1
    length = line_vec.length
    nx = -line_vec.y / length
    ny = line_vec.x / length
    d = abs((center.x - v1.x) * nx + (center.y - v1.y) * ny)
    check(abs(d - 1.0) < 1e-3, "tangent constraint failed")


def test_solver_diagnostics_and_selection():
    obj = new_sketch()
    v_indices, _ = build_mesh(obj, [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)], [])
    add_fix(obj, v_indices[0])
    add_fix(obj, v_indices[1])
    select(obj, verts=[v_indices[0], v_indices[1]])
    result = bpy.ops.aihelper.add_distance_constraint(distance=1.0005)
    check("FINISHED" in result, "add_distance_constraint failed")

    props = bpy.context.scene.ai_helper
    check(props.last_solver_report.startswith("WARN"), "solver report not warning")
    check(bool(props.last_solver_details), "solver details missing")
    check(bool(props.last_solver_worst_id), "solver worst id missing")

    constraints = load_constraints(obj)
    distance_constraint = next((c for c in constraints if getattr(c, "kind", "") == "distance"), None)
    check(distance_constraint is not None, "distance constraint missing")
    check(distance_constraint.id == props.last_solver_worst_id, "worst id mismatch")

    result = bpy.ops.aihelper.select_constraint(constraint_id=distance_constraint.id)
    check("FINISHED" in result, "select_constraint failed")
    check(sorted(selected_vertex_indices(obj)) == sorted(v_indices), "select constraint vertices failed")

    clear_selection(obj)
    result = bpy.ops.aihelper.select_worst_constraint()
    check("FINISHED" in result, "select_worst_constraint failed")
    check(sorted(selected_vertex_indices(obj)) == sorted(v_indices), "select worst constraint vertices failed")

    result = bpy.ops.aihelper.clear_solver_report()
    check("FINISHED" in result, "clear_solver_report failed")
    check(
        props.last_solver_report == ""
        and props.last_solver_details == ""
        and props.last_solver_worst_id == "",
        "clear diagnostics failed",
    )


def test_extrude_rebuild():
    obj = new_sketch()
    build_mesh(obj, [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)], [(0, 1)])
    result = bpy.ops.aihelper.extrude_sketch(distance=2.0)
    check("FINISHED" in result, "extrude_sketch failed")
    extrude_obj = next((o for o in bpy.data.objects if o.get("ai_helper_op") == "extrude"), None)
    check(extrude_obj is not None, "extrude object missing")
    check(abs(float(extrude_obj.get("ai_helper_extrude_distance", 0.0)) - 2.0) < 1e-4, "extrude distance missing")
    max_z = max(v.co.z for v in extrude_obj.data.vertices)
    check(abs(max_z - 2.0) < 1e-3, "extrude height incorrect")

    extrude_obj["ai_helper_extrude_distance"] = 3.0
    result = bpy.ops.aihelper.rebuild_3d_ops()
    check("FINISHED" in result, "rebuild_3d_ops failed for extrude")
    max_z = max(v.co.z for v in extrude_obj.data.vertices)
    check(abs(max_z - 3.0) < 1e-3, "extrude rebuild incorrect")


def test_extrude_selection():
    obj = new_sketch()
    build_mesh(obj, [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 1.0, 0.0)], [(0, 1), (1, 2)])
    select(obj, edges=[0])
    selected = [edge.index for edge in obj.data.edges if edge.select]
    check(selected, "extrude selection test missing selected edges")
    before = {o.name for o in bpy.data.objects}
    result = bpy.ops.aihelper.extrude_sketch(distance=1.0, use_selection=True)
    check("FINISHED" in result, "extrude_sketch selection failed")
    new_names = [name for name in bpy.data.objects.keys() if name not in before]
    extrude_obj = None
    for name in new_names:
        candidate = bpy.data.objects.get(name)
        if candidate and candidate.get("ai_helper_op") == "extrude":
            extrude_obj = candidate
            break
    check(extrude_obj is not None, "extrude object missing for selection")
    stored = extrude_obj.get("ai_helper_extrude_edges")
    stored_indices = list(stored) if stored is not None else []
    check(sorted(stored_indices) == sorted(selected), "extrude selection indices not stored")


def test_revolve_rebuild():
    obj = new_sketch()
    build_mesh(obj, [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)], [(0, 1)])
    result = bpy.ops.aihelper.revolve_sketch(angle=180.0, steps=16)
    check("FINISHED" in result, "revolve_sketch failed")
    revolve_obj = next((o for o in bpy.data.objects if o.get("ai_helper_op") == "revolve"), None)
    check(revolve_obj is not None, "revolve object missing")
    check(abs(float(revolve_obj.get("ai_helper_revolve_angle", 0.0)) - 180.0) < 1e-4, "revolve angle missing")
    check(int(revolve_obj.get("ai_helper_revolve_steps", 0)) == 16, "revolve steps missing")
    mod = revolve_obj.modifiers.get("AI_Revolve")
    check(mod is not None, "revolve modifier missing")
    check(abs(mod.angle - math.radians(180.0)) < 1e-5, "revolve modifier angle incorrect")
    check(mod.steps == 16, "revolve modifier steps incorrect")

    revolve_obj["ai_helper_revolve_angle"] = 90.0
    revolve_obj["ai_helper_revolve_steps"] = 8
    result = bpy.ops.aihelper.rebuild_3d_ops()
    check("FINISHED" in result, "rebuild_3d_ops failed for revolve")
    mod = revolve_obj.modifiers.get("AI_Revolve")
    check(mod is not None, "revolve modifier missing after rebuild")
    check(abs(mod.angle - math.radians(90.0)) < 1e-5, "revolve rebuild angle incorrect")
    check(mod.steps == 8, "revolve rebuild steps incorrect")


def test_shell_and_bevel_modifiers():
    obj = new_sketch()
    build_mesh(obj, [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)], [(0, 1)])
    result = bpy.ops.aihelper.extrude_sketch(distance=1.0)
    check("FINISHED" in result, "extrude_sketch failed for modifiers")
    extrude_obj = next((o for o in bpy.data.objects if o.get("ai_helper_op") == "extrude"), None)
    check(extrude_obj is not None, "extrude object missing for modifiers")

    bpy.context.view_layer.objects.active = extrude_obj
    result = bpy.ops.aihelper.add_shell_modifier(thickness=0.2)
    check("FINISHED" in result, "add_shell_modifier failed")
    mod = extrude_obj.modifiers.get("AI_Shell")
    check(mod is not None, "shell modifier missing")
    check(abs(mod.thickness - 0.2) < 1e-4, "shell thickness incorrect")

    result = bpy.ops.aihelper.add_bevel_modifier(width=0.1, segments=3)
    check("FINISHED" in result, "add_bevel_modifier failed")
    mod = extrude_obj.modifiers.get("AI_Bevel")
    check(mod is not None, "bevel modifier missing")
    check(abs(mod.width - 0.1) < 1e-4, "bevel width incorrect")
    check(mod.segments == 3, "bevel segments incorrect")

    extrude_obj["ai_helper_shell_thickness"] = 0.3
    extrude_obj["ai_helper_bevel_width"] = 0.05
    extrude_obj["ai_helper_bevel_segments"] = 1
    result = bpy.ops.aihelper.rebuild_3d_ops()
    check("FINISHED" in result, "rebuild_3d_ops failed for modifiers")
    mod = extrude_obj.modifiers.get("AI_Shell")
    check(mod is not None and abs(mod.thickness - 0.3) < 1e-4, "shell rebuild incorrect")
    mod = extrude_obj.modifiers.get("AI_Bevel")
    check(mod is not None and abs(mod.width - 0.05) < 1e-4, "bevel rebuild incorrect")
    check(mod.segments == 1, "bevel rebuild segments incorrect")

    result = bpy.ops.aihelper.clear_shell_modifier()
    check("FINISHED" in result, "clear_shell_modifier failed")
    result = bpy.ops.aihelper.clear_bevel_modifier()
    check("FINISHED" in result, "clear_bevel_modifier failed")
    check(extrude_obj.modifiers.get("AI_Shell") is None, "shell modifier not removed")
    check(extrude_obj.modifiers.get("AI_Bevel") is None, "bevel modifier not removed")


def test_loft_profiles():
    obj = new_sketch()
    result = bpy.ops.aihelper.add_rectangle(
        width=2.0,
        height=1.0,
        center_x=0.0,
        center_y=0.0,
        rotation_deg=0.0,
        tag="profile_a",
    )
    check("FINISHED" in result, "add_rectangle failed for loft A")
    result = bpy.ops.aihelper.add_rectangle(
        width=1.0,
        height=0.5,
        center_x=0.0,
        center_y=0.0,
        rotation_deg=0.0,
        tag="profile_b",
    )
    check("FINISHED" in result, "add_rectangle failed for loft B")
    result = bpy.ops.aihelper.loft_profiles(profile_a_tag="profile_a", profile_b_tag="profile_b", offset_z=2.0)
    check("FINISHED" in result, "loft_profiles failed")
    loft_obj = next((o for o in bpy.data.objects if o.get("ai_helper_op") == "loft"), None)
    check(loft_obj is not None, "loft object missing")
    max_z = max(v.co.z for v in loft_obj.data.vertices)
    check(abs(max_z - 2.0) < 1e-3, "loft height incorrect")

    loft_obj["ai_helper_loft_offset_z"] = 3.0
    result = bpy.ops.aihelper.rebuild_3d_ops()
    check("FINISHED" in result, "rebuild_3d_ops failed for loft")
    max_z = max(v.co.z for v in loft_obj.data.vertices)
    check(abs(max_z - 3.0) < 1e-3, "loft rebuild incorrect")


def test_loft_multi_profiles():
    obj = new_sketch()
    result = bpy.ops.aihelper.add_rectangle(
        width=2.0,
        height=1.0,
        center_x=0.0,
        center_y=0.0,
        rotation_deg=0.0,
        tag="profile_a",
    )
    check("FINISHED" in result, "add_rectangle failed for multi loft A")
    result = bpy.ops.aihelper.add_rectangle(
        width=1.5,
        height=0.8,
        center_x=0.0,
        center_y=0.0,
        rotation_deg=0.0,
        tag="profile_b",
    )
    check("FINISHED" in result, "add_rectangle failed for multi loft B")
    result = bpy.ops.aihelper.add_rectangle(
        width=1.0,
        height=0.5,
        center_x=0.0,
        center_y=0.0,
        rotation_deg=0.0,
        tag="profile_c",
    )
    check("FINISHED" in result, "add_rectangle failed for multi loft C")
    result = bpy.ops.aihelper.loft_profiles(profile_tags="profile_a, profile_b, profile_c", offset_z=1.0)
    check("FINISHED" in result, "loft_profiles failed for multi")
    loft_obj = next((o for o in bpy.data.objects if o.get("ai_helper_op") == "loft"), None)
    check(loft_obj is not None, "multi loft object missing")
    max_z = max(v.co.z for v in loft_obj.data.vertices)
    check(abs(max_z - 2.0) < 1e-3, "multi loft height incorrect")

    loft_obj["ai_helper_loft_offset_z"] = 1.5
    result = bpy.ops.aihelper.rebuild_3d_ops()
    check("FINISHED" in result, "rebuild_3d_ops failed for multi loft")
    max_z = max(v.co.z for v in loft_obj.data.vertices)
    check(abs(max_z - 3.0) < 1e-3, "multi loft rebuild incorrect")


def test_sweep_profile():
    obj = new_sketch()
    result = bpy.ops.aihelper.add_rectangle(
        width=2.0,
        height=1.0,
        center_x=0.0,
        center_y=0.0,
        rotation_deg=0.0,
        tag="profile",
    )
    check("FINISHED" in result, "add_rectangle failed for sweep profile")
    result = bpy.ops.aihelper.add_polyline(
        points="0.0,0.0; 2.0,0.0; 2.0,2.0",
        auto_constraints=False,
        tag="path",
    )
    check("FINISHED" in result, "add_polyline failed for sweep path")
    result = bpy.ops.aihelper.sweep_profile(profile_tag="profile", path_tag="path")
    check("FINISHED" in result, "sweep_profile failed")
    sweep_obj = next((o for o in bpy.data.objects if o.get("ai_helper_op") == "sweep"), None)
    check(sweep_obj is not None, "sweep object missing")
    coords = [v.co for v in sweep_obj.data.vertices]
    max_x = max(c.x for c in coords)
    max_y = max(c.y for c in coords)
    max_z = max(c.z for c in coords)
    check(max_x > 2.5, "sweep did not follow path in X")
    check(max_y >= 2.0, "sweep did not follow path in Y")
    check(max_z > 0.1, "sweep did not lift profile into Z")

    tags = load_tags(obj)
    path_entry = tags.get("path", {})
    edge_ids = [int(e) for e in path_entry.get("edges", [])]
    check(edge_ids, "sweep path edge missing")
    vert_ids = {vid for eid in edge_ids for vid in obj.data.edges[eid].vertices}
    end_vertex = max((obj.data.vertices[vid] for vid in vert_ids), key=lambda v: v.co.y)
    end_vertex.co.x = 3.0
    obj.data.update()
    result = bpy.ops.aihelper.rebuild_3d_ops()
    check("FINISHED" in result, "rebuild_3d_ops failed for sweep")
    new_max_x = max(v.co.x for v in sweep_obj.data.vertices)
    check(new_max_x > max_x + 0.5, "sweep rebuild incorrect")


def test_history_snapshot_restore():
    obj = new_sketch()
    build_mesh(obj, [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)], [(0, 1)])
    snapshot_state(obj, "Step 1")

    obj.data.vertices[1].co.x = 3.0
    obj.data.update()
    select(obj, edges=[0])
    result = bpy.ops.aihelper.add_distance_constraint(distance=2.0)
    check("FINISHED" in result, "add_distance_constraint failed for history")
    snapshot_state(obj, "Step 2")

    history = load_history(obj)
    check(len(history) >= 2, "history length incorrect")
    result = bpy.ops.aihelper.restore_snapshot(index=0)
    check("FINISHED" in result, "restore_snapshot failed")
    v1 = obj.data.vertices[1].co
    check(abs(v1.x - 1.0) < 1e-3, "history restore vertex incorrect")
    constraints = load_constraints(obj)
    check(len(constraints) == 0, "history restore constraints incorrect")


def test_llm_auto_constraints():
    obj = new_sketch()
    v_indices, e_indices = build_mesh(obj, [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)], [(0, 1)])
    select(obj, edges=[e_indices[0]])
    tool_calls = [{"name": "add_constraint", "arguments": {"kind": "horizontal"}}]
    result = dispatch_tool_calls(tool_calls, bpy.context, preview=False)
    check(not result["errors"], "llm add_constraint errors")
    constraints = load_constraints(obj)
    check(len(constraints) == 1, "llm constraint not added")


def test_llm_sketch_generation():
    obj = new_sketch()
    tool_calls = [
        {"name": "add_line", "arguments": {"start_x": 0.0, "start_y": 0.0, "end_x": 2.0, "end_y": 0.0, "tag": "base"}},
        {"name": "add_circle", "arguments": {"center_x": 1.0, "center_y": 1.0, "radius": 0.5, "tag": "hole"}},
        {"name": "select_sketch_entities", "arguments": {"tags": ["base"]}},
        {"name": "add_constraint", "arguments": {"kind": "distance", "distance": 2.0}},
        {"name": "select_sketch_entities", "arguments": {"tags": ["hole"]}},
        {"name": "add_constraint", "arguments": {"kind": "radius", "radius": 0.5}},
    ]
    result = dispatch_tool_calls(tool_calls, bpy.context, preview=False)
    check(not result["errors"], "llm sketch tool errors")
    constraints = load_constraints(obj)
    check(len(constraints) >= 2, "llm sketch constraints missing")
    tags = load_tags(obj)
    check("base" in tags and "hole" in tags, "llm tags missing")

    result = dispatch_tool_calls([{"name": "clear_sketch", "arguments": {}}], bpy.context, preview=False)
    check(not result["errors"], "llm clear_sketch errors")
    check(len(obj.data.vertices) == 0 and len(obj.data.edges) == 0, "clear_sketch did not clear mesh")
    check(len(load_constraints(obj)) == 0, "clear_sketch did not clear constraints")


def test_llm_polyline_rectangle():
    obj = new_sketch()
    tool_calls = [
        {
            "name": "add_rectangle",
            "arguments": {
                "center_x": 0.0,
                "center_y": 0.0,
                "width": 2.0,
                "height": 1.0,
                "rotation_deg": 30.0,
                "tag": "rect",
            },
        },
        {"name": "add_polyline", "arguments": {"points": [[3.0, 0.0], [4.0, 0.0], [4.0, 1.0]], "tag": "pline"}},
    ]
    result = dispatch_tool_calls(tool_calls, bpy.context, preview=False)
    check(not result["errors"], "llm polyline/rectangle errors")
    tags = load_tags(obj)
    check("rect" in tags and "pline" in tags, "llm polyline/rectangle tags missing")
    check(len(obj.data.edges) >= 6, "llm polyline/rectangle edges missing")


def test_llm_arc():
    obj = new_sketch()
    tool_calls = [
        {
            "name": "add_arc",
            "arguments": {"center_x": 0.0, "center_y": 0.0, "radius": 1.0, "start_angle": 0.0, "end_angle": 90.0, "tag": "arc"},
        }
    ]
    result = dispatch_tool_calls(tool_calls, bpy.context, preview=False)
    check(not result["errors"], "llm arc errors")
    circles = load_circles(obj)
    check(len(circles) == 1, "llm arc circle missing")
    circle = circles[0]
    check(circle.get("is_arc") is True, "llm arc flag missing")
    check(len(obj.data.edges) >= 1, "llm arc edges missing")


def test_edit_arc_operator():
    obj = new_sketch()
    result = bpy.ops.aihelper.add_arc(
        radius=1.0,
        center_x=0.0,
        center_y=0.0,
        start_angle=0.0,
        end_angle=90.0,
        segments=8,
    )
    check("FINISHED" in result, "add_arc operator failed")
    select(obj, edges=[0])
    result = bpy.ops.aihelper.edit_arc(
        radius=2.0,
        center_x=1.0,
        center_y=0.0,
        start_angle=0.0,
        end_angle=180.0,
    )
    check("FINISHED" in result, "edit_arc operator failed")
    circles = load_circles(obj)
    check(len(circles) == 1, "edit_arc circle missing")
    circle = circles[0]
    check(abs(circle.get("radius", 0.0) - 2.0) < 1e-4, "edit_arc radius not updated")
    center_idx = int(circle.get("center"))
    center = obj.data.vertices[center_idx].co
    vert_id = int(circle.get("verts", [0])[0])
    vert = obj.data.vertices[vert_id].co
    dist = (vert - center).length
    check(abs(dist - 2.0) < 1e-3, "edit_arc geometry not updated")


def test_llm_edit_arc():
    obj = new_sketch()
    tool_calls = [
        {
            "name": "add_arc",
            "arguments": {
                "center_x": 0.0,
                "center_y": 0.0,
                "radius": 1.0,
                "start_angle": 0.0,
                "end_angle": 90.0,
                "tag": "arc",
            },
        },
        {
            "name": "edit_arc",
            "arguments": {
                "tag": "arc",
                "radius": 2.0,
                "start_angle": 0.0,
                "end_angle": 180.0,
            },
        },
    ]
    result = dispatch_tool_calls(tool_calls, bpy.context, preview=False)
    check(not result["errors"], "llm edit_arc errors")
    circles = load_circles(obj)
    check(len(circles) == 1, "llm edit_arc circle missing")
    circle = circles[0]
    check(abs(circle.get("radius", 0.0) - 2.0) < 1e-4, "llm edit_arc radius not updated")
    check(abs(circle.get("start_angle", 0.0) - 0.0) < 1e-4, "llm edit_arc start angle not updated")
    check(abs(circle.get("end_angle", 0.0) - 180.0) < 1e-4, "llm edit_arc end angle not updated")


def test_edit_rectangle_operator():
    obj = new_sketch()
    result = bpy.ops.aihelper.add_rectangle(
        width=2.0,
        height=1.0,
        center_x=0.0,
        center_y=0.0,
        rotation_deg=0.0,
    )
    check("FINISHED" in result, "add_rectangle operator failed")
    rects = load_rectangles(obj)
    check(len(rects) == 1, "rectangle metadata missing")
    rect = rects[0]
    vert_ids = [int(v) for v in rect.get("verts", [])]
    orig_coords = [obj.data.vertices[vid].co.copy() for vid in vert_ids]

    select(obj, edges=[0])
    result = bpy.ops.aihelper.edit_rectangle(
        width=4.0,
        height=2.0,
        center_x=1.0,
        center_y=1.0,
        rotation_deg=30.0,
    )
    check("FINISHED" in result, "edit_rectangle operator failed")
    rects = load_rectangles(obj)
    rect = rects[0]
    center = rect.get("center", [0.0, 0.0])
    check(abs(center[0] - 1.0) < 1e-3 and abs(center[1] - 1.0) < 1e-3, "rectangle center not updated")
    check(rect.get("width", 0.0) > 0.0 and rect.get("height", 0.0) > 0.0, "rectangle size invalid")
    coords = [obj.data.vertices[vid].co for vid in vert_ids]
    moved = any((coords[idx] - orig_coords[idx]).length > 0.1 for idx in range(len(coords)))
    check(moved, "rectangle vertices did not move")


def test_llm_edit_rectangle():
    obj = new_sketch()
    tool_calls = [
        {
            "name": "add_rectangle",
            "arguments": {
                "center_x": 0.0,
                "center_y": 0.0,
                "width": 2.0,
                "height": 1.0,
                "rotation_deg": 0.0,
                "tag": "rect",
            },
        },
        {
            "name": "edit_rectangle",
            "arguments": {
                "tag": "rect",
                "center_x": 1.0,
                "center_y": 1.0,
                "width": 4.0,
                "height": 2.0,
                "rotation_deg": 30.0,
            },
        },
    ]
    result = dispatch_tool_calls(tool_calls, bpy.context, preview=False)
    check(not result["errors"], "llm edit_rectangle errors")
    rects = load_rectangles(obj)
    check(len(rects) == 1, "llm rectangle metadata missing")
    rect = rects[0]
    center = rect.get("center", [0.0, 0.0])
    check(abs(center[0] - 1.0) < 1e-3 and abs(center[1] - 1.0) < 1e-3, "llm rectangle center not updated")
    check(rect.get("width", 0.0) > 0.0 and rect.get("height", 0.0) > 0.0, "llm rectangle size invalid")


def test_llm_image_prompt_mock():
    temp_path = Path(tempfile.gettempdir()) / "ai_helper_mock_image.txt"
    temp_path.write_text("mock image data")
    adapter = GrokAdapter(adapter_path=None, mock=True)
    calls = adapter.request_tool_calls(
        "sketch from image",
        {"objects": []},
        use_mock=True,
        image_path=str(temp_path),
        image_notes="base",
    )
    check(calls and calls[0].name in ("add_line", "add_circle"), "llm image mock failed")
    try:
        temp_path.unlink()
    except FileNotFoundError:
        pass

    adapter = GrokAdapter(adapter_path=None, mock=True)
    calls = adapter.request_tool_calls(
        "sketch from image url",
        {"objects": []},
        use_mock=True,
        image_path="https://example.com/image.png",
        image_notes="url",
    )
    check(calls and calls[0].name in ("add_line", "add_circle"), "llm image url mock failed")


def test_prompt_preset_operator():
    props = bpy.context.scene.ai_helper
    props.prompt = ""
    props.prompt_preset = "PLATE_4_HOLES"
    result = bpy.ops.aihelper.apply_prompt_preset(append=False)
    check("FINISHED" in result, "apply_prompt_preset failed")
    check("rectangular plate" in props.prompt, "preset prompt not applied")

    props.prompt = "Base prompt"
    props.prompt_preset = "L_BRACKET"
    result = bpy.ops.aihelper.apply_prompt_preset(append=True)
    check("FINISHED" in result, "append prompt preset failed")
    check("Base prompt" in props.prompt and "L-shaped" in props.prompt, "append preset missing content")


def test_prompt_recipe_operator():
    props = bpy.context.scene.ai_helper
    props.prompt = ""
    props.prompt_recipe = "SKETCH_FROM_NOTES"
    result = bpy.ops.aihelper.apply_prompt_recipe(append=False)
    check("FINISHED" in result, "apply_prompt_recipe failed")
    check("clean 2D sketch" in props.prompt, "recipe prompt not applied")

    props.prompt = "Base prompt"
    props.prompt_recipe = "AUTO_CONSTRAIN"
    result = bpy.ops.aihelper.apply_prompt_recipe(append=True)
    check("FINISHED" in result, "append prompt recipe failed")
    check("Base prompt" in props.prompt and "horizontal/vertical" in props.prompt, "append recipe missing content")


def test_param_preset_operator():
    props = bpy.context.scene.ai_helper
    props.prompt = ""
    props.prompt_preset = "PLATE_4_HOLES"
    result = bpy.ops.aihelper.apply_param_preset(
        append=False,
        width=120.0,
        height=80.0,
        hole_radius=6.0,
        hole_offset_x=40.0,
        hole_offset_y=20.0,
    )
    check("FINISHED" in result, "apply_param_preset failed")
    check("120x80" in props.prompt, "param preset width/height missing")
    check("radius 6" in props.prompt, "param preset radius missing")

    props.prompt = ""
    props.prompt_preset = "BOLT_CIRCLE"
    result = bpy.ops.aihelper.apply_param_preset(
        append=False,
        bolt_count=8.0,
        bolt_circle_radius=50.0,
        bolt_hole_radius=4.0,
    )
    check("FINISHED" in result, "apply_param_preset bolt circle failed")
    check("8 holes" in props.prompt, "bolt circle count missing")
    check("radius 4" in props.prompt, "bolt circle hole radius missing")


def test_preferences_fields():
    addon = bpy.context.preferences.addons.get("ai_helper")
    if addon is None:
        return
    prefs = addon.preferences
    check(hasattr(prefs, "grok_model"), "prefs missing grok_model")
    check(hasattr(prefs, "grok_vision_model"), "prefs missing grok_vision_model")
    check(hasattr(prefs, "grok_vision_image_url"), "prefs missing grok_vision_image_url")
    check(hasattr(prefs, "grok_vision_upload_command"), "prefs missing grok_vision_upload_command")
    check(hasattr(prefs, "grok_vision_upload_timeout"), "prefs missing grok_vision_upload_timeout")
    prefs.grok_model = "grok-4-1-fast-reasoning"
    prefs.grok_vision_model = "grok-4-1-fast-reasoning"
    prefs.grok_vision_image_url = "https://example.com/image.png"
    check("grok-4-1" in prefs.grok_model, "prefs grok_model not set")


def test_install_deps_operator_exists():
    check(hasattr(bpy.ops.aihelper, "install_grok_deps"), "install_grok_deps operator missing")


def test_upload_command_parsing():
    temp_path = Path(tempfile.gettempdir()) / "ai_helper_upload_mock.txt"
    temp_path.write_text("mock")
    exe_name = os.path.basename(sys.executable or "")
    if Path("/bin/echo").exists():
        cmd = "/bin/echo https://example.com/upload.png"
    elif "python" in exe_name:
        cmd = f"{sys.executable} -c \"print('https://example.com/upload.png')\""
    elif os.name != "nt":
        cmd = "sh -c \"printf 'https://example.com/upload.png'\""
    else:
        temp_path.unlink(missing_ok=True)
        return
    adapter = GrokAdapter(adapter_path=None, mock=True)
    calls = adapter.request_tool_calls(
        "sketch from upload",
        {"objects": []},
        use_mock=True,
        image_path=str(temp_path),
        upload_command=cmd,
    )
    check(calls and calls[0].name in ("add_line", "add_circle"), "upload command mock failed")
    try:
        temp_path.unlink()
    except FileNotFoundError:
        pass


def test_tag_selection_operator():
    obj = new_sketch()
    _verts, _edges = build_mesh(obj, [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)], [(0, 1)])
    register_tag(obj, "edge_tag", verts=[0, 1], edges=[0])
    result = bpy.ops.aihelper.select_tag(tag="edge_tag", extend=False)
    check("FINISHED" in result, "select_tag failed")
    sel_verts = selected_vertex_indices(obj)
    sel_edges = [e.index for e in obj.data.edges if e.select]
    check(sel_verts == [], "tag selection verts mismatch")
    check(sel_edges == [0], "tag selection edges mismatch")


def test_auto_rebuild_handler():
    obj = new_sketch()
    build_mesh(obj, [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)], [(0, 1)])
    result = bpy.ops.aihelper.extrude_sketch(distance=1.0)
    check("FINISHED" in result, "extrude_sketch failed for auto rebuild")
    extrude_obj = next((o for o in bpy.data.objects if o.get("ai_helper_op") == "extrude"), None)
    check(extrude_obj is not None, "extrude object missing for auto rebuild")

    obj.data.vertices[1].co.x = 2.0
    obj.data.update()

    props = bpy.context.scene.ai_helper
    props.auto_rebuild = True

    from ai_helper.core import handlers  # noqa: E402

    update = types.SimpleNamespace(id=obj, is_updated_geometry=True, is_updated_data=False)
    depsgraph = types.SimpleNamespace(updates=[update])
    handlers.ai_helper_depsgraph_handler(bpy.context.scene, depsgraph)
    check(handlers._PENDING_REBUILD, "auto rebuild not scheduled")
    handlers._run_rebuild(bpy.context.scene)

    xs = [round(v.co.x, 4) for v in extrude_obj.data.vertices]
    check(any(abs(x - 2.0) < 1e-3 for x in xs), "auto rebuild did not update extrude")


def run():
    ai_helper.register()
    test_precision_vertex_coords()
    test_precision_edge_length()
    test_precision_edge_angle()
    test_inspector_vertex()
    test_inspector_edge()
    test_inspector_arc()
    test_inspector_rectangle()
    test_midpoint_constraint()
    test_equal_length_constraint()
    test_coincident_constraint()
    test_parallel_constraint()
    test_perpendicular_constraint()
    test_angle_constraint_edit()
    test_sketch_input_and_preview()
    test_sketch_snapping()
    test_sketch_axis_lock_and_angle_snap()
    test_constraint_dialog_prefill()
    test_symmetry_constraint()
    test_circle_constraints()
    test_tangent_constraint()
    test_solver_diagnostics_and_selection()
    test_extrude_rebuild()
    test_revolve_rebuild()
    test_shell_and_bevel_modifiers()
    test_loft_profiles()
    test_loft_multi_profiles()
    test_sweep_profile()
    test_extrude_selection()
    test_history_snapshot_restore()
    test_llm_auto_constraints()
    test_llm_sketch_generation()
    test_llm_polyline_rectangle()
    test_llm_arc()
    test_edit_arc_operator()
    test_llm_edit_arc()
    test_llm_image_prompt_mock()
    test_edit_rectangle_operator()
    test_llm_edit_rectangle()
    test_prompt_preset_operator()
    test_prompt_recipe_operator()
    test_param_preset_operator()
    test_preferences_fields()
    test_install_deps_operator_exists()
    test_upload_command_parsing()
    test_tag_selection_operator()
    test_auto_rebuild_handler()
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    run()
