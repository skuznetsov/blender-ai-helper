import math
import os
import sys

import bpy
import bmesh
from mathutils import Vector


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import ai_helper  # noqa: E402
from ai_helper.sketch.circles import load_circles  # noqa: E402
from ai_helper.sketch.constraints import AngleConstraint, RadiusConstraint  # noqa: E402
from ai_helper.sketch.store import load_constraints  # noqa: E402


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


def run():
    ai_helper.register()
    test_precision_vertex_coords()
    test_precision_edge_length()
    test_precision_edge_angle()
    test_midpoint_constraint()
    test_equal_length_constraint()
    test_coincident_constraint()
    test_parallel_constraint()
    test_perpendicular_constraint()
    test_angle_constraint_edit()
    test_symmetry_constraint()
    test_circle_constraints()
    test_tangent_constraint()
    test_solver_diagnostics_and_selection()
    test_extrude_rebuild()
    test_revolve_rebuild()
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    run()
