import math

import bpy
import bmesh
from ..sketch.constraints import (
    AngleConstraint,
    CoincidentConstraint,
    ConcentricConstraint,
    DistanceConstraint,
    FixConstraint,
    HorizontalConstraint,
    EqualLengthConstraint,
    ParallelConstraint,
    PerpendicularConstraint,
    RadiusConstraint,
    SymmetryConstraint,
    MidpointConstraint,
    VerticalConstraint,
)
from ..sketch.circles import (
    find_circle,
    find_circle_by_center,
    find_circle_by_vertex,
    load_circles,
    update_circle_radius,
)
from ..sketch.dimensions import (
    clear_dimensions,
    get_dimension_constraint_id,
    get_dimension_kind,
    update_dimensions,
)
from ..sketch.solver_bridge import solve_mesh
from ..sketch.store import (
    append_constraint,
    clear_constraints,
    load_constraints,
    new_constraint_id,
    remove_constraint,
    update_constraint,
)


def _get_sketch_object(context):
    obj = context.scene.objects.get("AI_Sketch")
    if obj is None or obj.type != "MESH":
        return None
    return obj


def _selected_edge(obj):
    for edge in obj.data.edges:
        if edge.select:
            return edge
    return None


def _selected_edges(obj):
    return [edge for edge in obj.data.edges if edge.select]


def _shared_vertex_for_edges(edges):
    if len(edges) != 2:
        return None
    verts_a = set(edges[0].vertices)
    verts_b = set(edges[1].vertices)
    shared = verts_a & verts_b
    if not shared:
        return None
    vertex = shared.pop()
    other_a = (verts_a - {vertex}).pop()
    other_b = (verts_b - {vertex}).pop()
    return other_a, vertex, other_b


def _selected_vertices(obj):
    return [v for v in obj.data.vertices if v.select]


def _selected_vertices_excluding_edge(obj, edge):
    if edge is None:
        return _selected_vertices(obj)
    excluded = set(edge.vertices)
    return [v for v in _selected_vertices(obj) if v.index not in excluded]


def _distance_targets(obj):
    edge = _selected_edge(obj)
    if edge is not None:
        v1 = obj.data.vertices[edge.vertices[0]]
        v2 = obj.data.vertices[edge.vertices[1]]
        return v1, v2

    verts = _selected_vertices(obj)
    if len(verts) == 2:
        return verts[0], verts[1]
    return None


def _angle_targets(obj):
    edges = _selected_edges(obj)
    shared = _shared_vertex_for_edges(edges)
    if shared is None:
        return None

    p1, vertex, p2 = shared
    try:
        v1 = obj.data.vertices[p1]
        vtx = obj.data.vertices[vertex]
        v2 = obj.data.vertices[p2]
    except IndexError:
        return None

    v1_vec = v1.co - vtx.co
    v2_vec = v2.co - vtx.co
    len1 = v1_vec.length
    len2 = v2_vec.length
    if len1 < 1e-8 or len2 < 1e-8:
        return None

    dot = v1_vec.dot(v2_vec)
    cos_val = max(-1.0, min(1.0, dot / (len1 * len2)))
    angle_deg = math.degrees(math.acos(cos_val))
    return p1, vertex, p2, angle_deg


def _circle_current_radius(obj, circle):
    center_id = circle.get("center")
    vert_ids = circle.get("verts", [])
    if center_id is None or not vert_ids:
        return None

    try:
        center = obj.data.vertices[int(center_id)].co
    except (ValueError, IndexError):
        return None

    radius = float(circle.get("radius", 0.0))
    if radius > 0.0:
        return radius

    total = 0.0
    count = 0
    for vid in vert_ids:
        try:
            vert = obj.data.vertices[int(vid)]
        except (ValueError, IndexError):
            continue
        total += (vert.co - center).length
        count += 1
    if count == 0:
        return None
    return total / count


def _selected_circle(obj):
    circles = load_circles(obj)
    if not circles:
        return None

    for vert in obj.data.vertices:
        if not vert.select:
            continue
        circle = find_circle_by_vertex(circles, str(vert.index))
        if circle:
            return circle
        circle = find_circle_by_center(circles, str(vert.index))
        if circle:
            return circle

    for edge in obj.data.edges:
        if not edge.select:
            continue
        for vid in edge.vertices:
            circle = find_circle_by_vertex(circles, str(vid))
            if circle:
                return circle
    return None


def _selected_circles(obj):
    circles = load_circles(obj)
    if not circles:
        return []

    found = []
    seen = set()

    for vert in obj.data.vertices:
        if not vert.select:
            continue
        for circle in (
            find_circle_by_vertex(circles, str(vert.index)),
            find_circle_by_center(circles, str(vert.index)),
        ):
            if circle and circle.get("id") not in seen:
                seen.add(circle.get("id"))
                found.append(circle)

    for edge in obj.data.edges:
        if not edge.select:
            continue
        for vid in edge.vertices:
            circle = find_circle_by_vertex(circles, str(vid))
            if circle and circle.get("id") not in seen:
                seen.add(circle.get("id"))
                found.append(circle)

    return found


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


def _format_diag(diag):
    status = "OK" if diag.converged else "WARN"
    fallback = "yes" if diag.fallback_applied else "no"
    return f"{status} it={diag.iterations} err={diag.max_error:.4f} fallback={fallback}"


def _base_constraint_id(constraint_id):
    if not constraint_id:
        return ""
    return constraint_id.split(":", 1)[0]


def _format_diag_details(diag):
    lines = []
    for entry in diag.worst_constraints:
        base_id = _base_constraint_id(entry.constraint_id)
        cid = base_id or "?"
        short = cid[:6] if cid != "?" else cid
        lines.append(f"{entry.kind} {short} err={entry.error:.4f}")
    return "\n".join(lines)


def _update_solver_report(context, diag):
    props = context.scene.ai_helper
    props.last_solver_report = _format_diag(diag)
    props.last_solver_details = _format_diag_details(diag)
    props.last_solver_worst_id = _base_constraint_id(diag.worst_constraint_id)


def _select_constraint_geometry(obj, constraint, extend=False):
    verts = []
    edges = []
    if isinstance(constraint, DistanceConstraint):
        verts = [int(constraint.p1), int(constraint.p2)]
    elif isinstance(constraint, AngleConstraint):
        verts = [int(constraint.p1), int(constraint.vertex), int(constraint.p2)]
    elif isinstance(constraint, FixConstraint):
        verts = [int(constraint.point)]
    elif isinstance(constraint, CoincidentConstraint):
        verts = [int(constraint.p1), int(constraint.p2)]
    elif isinstance(constraint, RadiusConstraint):
        circles = load_circles(obj)
        circle = find_circle(circles, constraint.entity)
        if circle:
            verts = [int(v) for v in circle.get("verts", [])]
    elif isinstance(constraint, MidpointConstraint):
        edges = [int(constraint.line)]
        verts = [int(constraint.point)]
    elif isinstance(constraint, EqualLengthConstraint):
        edges = [int(constraint.line_a), int(constraint.line_b)]
    elif isinstance(constraint, ConcentricConstraint):
        verts = [int(constraint.p1), int(constraint.p2)]
    elif isinstance(constraint, SymmetryConstraint):
        edges = [int(constraint.line)]
        verts = [int(constraint.p1), int(constraint.p2)]
    elif isinstance(constraint, (HorizontalConstraint, VerticalConstraint)):
        edges = [int(constraint.line)]
    elif isinstance(constraint, (ParallelConstraint, PerpendicularConstraint)):
        edges = [int(constraint.line_a), int(constraint.line_b)]
    else:
        return False, "Constraint type not supported for selection"

    if not verts and not edges:
        return False, "No geometry found for constraint"

    _set_selection(obj, verts=verts, edges=edges, extend=extend)
    return True, ""


class AIHELPER_OT_add_distance_constraint(bpy.types.Operator):
    bl_idname = "aihelper.add_distance_constraint"
    bl_label = "Add Distance"
    bl_description = "Add a distance constraint to selected edge or vertices"
    bl_options = {"REGISTER", "UNDO"}

    distance: bpy.props.FloatProperty(
        name="Distance",
        description="Target distance (0 = keep current)",
        default=0.0,
        min=0.0,
    )

    def invoke(self, context, _event):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        targets = _distance_targets(obj)
        if targets is None:
            self.report({"WARNING"}, "Select 1 edge or 2 vertices")
            return {"CANCELLED"}

        v1, v2 = targets
        self.distance = (v2.co - v1.co).length
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        targets = _distance_targets(obj)
        if targets is None:
            self.report({"WARNING"}, "Select 1 edge or 2 vertices")
            return {"CANCELLED"}
        v1, v2 = targets

        current = (v2.co - v1.co).length
        target = self.distance if self.distance > 0.0 else current

        constraint = DistanceConstraint(
            id=new_constraint_id(),
            p1=str(v1.index),
            p2=str(v2.index),
            distance=target,
        )
        append_constraint(obj, constraint)

        diag = solve_mesh(obj, load_constraints(obj))
        update_dimensions(context, obj, load_constraints(obj))
        _update_solver_report(context, diag)

        self.report({"INFO"}, "Distance constraint added")
        return {"FINISHED"}


class AIHELPER_OT_add_horizontal_constraint(bpy.types.Operator):
    bl_idname = "aihelper.add_horizontal_constraint"
    bl_label = "Add Horizontal"
    bl_description = "Add a horizontal constraint to selected edge"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        edge = _selected_edge(obj)
        if edge is None:
            self.report({"WARNING"}, "Select 1 edge")
            return {"CANCELLED"}

        constraint = HorizontalConstraint(id=new_constraint_id(), line=str(edge.index))
        append_constraint(obj, constraint)

        diag = solve_mesh(obj, load_constraints(obj))
        update_dimensions(context, obj, load_constraints(obj))
        _update_solver_report(context, diag)

        self.report({"INFO"}, "Horizontal constraint added")
        return {"FINISHED"}


class AIHELPER_OT_add_vertical_constraint(bpy.types.Operator):
    bl_idname = "aihelper.add_vertical_constraint"
    bl_label = "Add Vertical"
    bl_description = "Add a vertical constraint to selected edge"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        edge = _selected_edge(obj)
        if edge is None:
            self.report({"WARNING"}, "Select 1 edge")
            return {"CANCELLED"}

        constraint = VerticalConstraint(id=new_constraint_id(), line=str(edge.index))
        append_constraint(obj, constraint)

        diag = solve_mesh(obj, load_constraints(obj))
        update_dimensions(context, obj, load_constraints(obj))
        _update_solver_report(context, diag)

        self.report({"INFO"}, "Vertical constraint added")
        return {"FINISHED"}


class AIHELPER_OT_add_angle_constraint(bpy.types.Operator):
    bl_idname = "aihelper.add_angle_constraint"
    bl_label = "Add Angle"
    bl_description = "Add an angle constraint between two connected edges"
    bl_options = {"REGISTER", "UNDO"}

    degrees: bpy.props.FloatProperty(
        name="Angle",
        description="Target angle in degrees",
        default=90.0,
        min=0.0,
        max=180.0,
    )

    def invoke(self, context, _event):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        targets = _angle_targets(obj)
        if targets is None:
            self.report({"WARNING"}, "Select 2 edges sharing a vertex")
            return {"CANCELLED"}

        _p1, _vertex, _p2, angle_deg = targets
        self.degrees = angle_deg
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        targets = _angle_targets(obj)
        if targets is None:
            self.report({"WARNING"}, "Select 2 edges sharing a vertex")
            return {"CANCELLED"}

        p1, vertex, p2, _angle_deg = targets
        constraint = AngleConstraint(
            id=new_constraint_id(),
            p1=str(p1),
            vertex=str(vertex),
            p2=str(p2),
            degrees=self.degrees,
        )
        append_constraint(obj, constraint)

        diag = solve_mesh(obj, load_constraints(obj))
        update_dimensions(context, obj, load_constraints(obj))
        _update_solver_report(context, diag)

        self.report({"INFO"}, "Angle constraint added")
        return {"FINISHED"}


class AIHELPER_OT_add_radius_constraint(bpy.types.Operator):
    bl_idname = "aihelper.add_radius_constraint"
    bl_label = "Add Radius"
    bl_description = "Add a radius constraint to a circle"
    bl_options = {"REGISTER", "UNDO"}

    radius: bpy.props.FloatProperty(
        name="Radius",
        description="Target radius",
        min=0.0,
        default=1.0,
    )

    def invoke(self, context, _event):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        circle = _selected_circle(obj)
        if circle is None:
            self.report({"WARNING"}, "Select a circle vertex or edge")
            return {"CANCELLED"}

        radius = _circle_current_radius(obj, circle)
        if radius is None:
            self.report({"WARNING"}, "Circle metadata missing")
            return {"CANCELLED"}

        self.radius = radius
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        circle = _selected_circle(obj)
        if circle is None:
            self.report({"WARNING"}, "Select a circle vertex or edge")
            return {"CANCELLED"}

        radius = self.radius
        if radius <= 0.0:
            radius = _circle_current_radius(obj, circle)
            if radius is None:
                self.report({"WARNING"}, "Circle metadata missing")
                return {"CANCELLED"}

        constraint = RadiusConstraint(
            id=new_constraint_id(),
            entity=str(circle["id"]),
            radius=radius,
        )
        append_constraint(obj, constraint)
        update_circle_radius(obj, constraint.entity, radius)

        diag = solve_mesh(obj, load_constraints(obj))
        update_dimensions(context, obj, load_constraints(obj))
        _update_solver_report(context, diag)

        self.report({"INFO"}, "Radius constraint added")
        return {"FINISHED"}


class AIHELPER_OT_add_coincident_constraint(bpy.types.Operator):
    bl_idname = "aihelper.add_coincident_constraint"
    bl_label = "Add Coincident"
    bl_description = "Make two selected vertices coincident"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        verts = _selected_vertices(obj)
        if len(verts) != 2:
            self.report({"WARNING"}, "Select 2 vertices")
            return {"CANCELLED"}

        constraint = CoincidentConstraint(
            id=new_constraint_id(),
            p1=str(verts[0].index),
            p2=str(verts[1].index),
        )
        append_constraint(obj, constraint)

        diag = solve_mesh(obj, load_constraints(obj))
        update_dimensions(context, obj, load_constraints(obj))
        _update_solver_report(context, diag)

        self.report({"INFO"}, "Coincident constraint added")
        return {"FINISHED"}


class AIHELPER_OT_add_midpoint_constraint(bpy.types.Operator):
    bl_idname = "aihelper.add_midpoint_constraint"
    bl_label = "Add Midpoint"
    bl_description = "Make a selected vertex the midpoint of a selected edge"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        edge = _selected_edge(obj)
        verts = _selected_vertices(obj)
        if edge is None or len(verts) != 1:
            self.report({"WARNING"}, "Select 1 edge and 1 vertex")
            return {"CANCELLED"}

        vertex = verts[0]
        if vertex.index in edge.vertices:
            self.report({"WARNING"}, "Select a vertex not on the edge")
            return {"CANCELLED"}

        constraint = MidpointConstraint(
            id=new_constraint_id(),
            line=str(edge.index),
            point=str(vertex.index),
        )
        append_constraint(obj, constraint)

        diag = solve_mesh(obj, load_constraints(obj))
        update_dimensions(context, obj, load_constraints(obj))
        _update_solver_report(context, diag)

        self.report({"INFO"}, "Midpoint constraint added")
        return {"FINISHED"}


class AIHELPER_OT_add_equal_length_constraint(bpy.types.Operator):
    bl_idname = "aihelper.add_equal_length_constraint"
    bl_label = "Add Equal Length"
    bl_description = "Make two selected edges have equal length"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        edges = _selected_edges(obj)
        if len(edges) != 2:
            self.report({"WARNING"}, "Select 2 edges")
            return {"CANCELLED"}

        constraint = EqualLengthConstraint(
            id=new_constraint_id(),
            line_a=str(edges[0].index),
            line_b=str(edges[1].index),
        )
        append_constraint(obj, constraint)

        diag = solve_mesh(obj, load_constraints(obj))
        update_dimensions(context, obj, load_constraints(obj))
        _update_solver_report(context, diag)

        self.report({"INFO"}, "Equal length constraint added")
        return {"FINISHED"}


class AIHELPER_OT_add_concentric_constraint(bpy.types.Operator):
    bl_idname = "aihelper.add_concentric_constraint"
    bl_label = "Add Concentric"
    bl_description = "Make two circles share the same center"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        circles = _selected_circles(obj)
        if len(circles) != 2:
            self.report({"WARNING"}, "Select 2 circles")
            return {"CANCELLED"}

        c1, c2 = circles
        center1 = c1.get("center")
        center2 = c2.get("center")
        if not center1 or not center2:
            self.report({"WARNING"}, "Circle metadata missing")
            return {"CANCELLED"}
        if center1 == center2:
            self.report({"WARNING"}, "Circles already concentric")
            return {"CANCELLED"}

        constraint = ConcentricConstraint(
            id=new_constraint_id(),
            p1=str(center1),
            p2=str(center2),
        )
        append_constraint(obj, constraint)

        diag = solve_mesh(obj, load_constraints(obj))
        update_dimensions(context, obj, load_constraints(obj))
        _update_solver_report(context, diag)

        self.report({"INFO"}, "Concentric constraint added")
        return {"FINISHED"}


class AIHELPER_OT_add_symmetry_constraint(bpy.types.Operator):
    bl_idname = "aihelper.add_symmetry_constraint"
    bl_label = "Add Symmetry"
    bl_description = "Make two vertices symmetric about a selected edge"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        edge = _selected_edge(obj)
        verts = _selected_vertices_excluding_edge(obj, edge)
        if edge is None or len(verts) != 2:
            self.report({"WARNING"}, "Select 1 edge and 2 vertices")
            return {"CANCELLED"}

        if verts[0].index == verts[1].index:
            self.report({"WARNING"}, "Select 2 distinct vertices")
            return {"CANCELLED"}

        constraint = SymmetryConstraint(
            id=new_constraint_id(),
            line=str(edge.index),
            p1=str(verts[0].index),
            p2=str(verts[1].index),
        )
        append_constraint(obj, constraint)

        diag = solve_mesh(obj, load_constraints(obj))
        update_dimensions(context, obj, load_constraints(obj))
        _update_solver_report(context, diag)

        self.report({"INFO"}, "Symmetry constraint added")
        return {"FINISHED"}


class AIHELPER_OT_add_parallel_constraint(bpy.types.Operator):
    bl_idname = "aihelper.add_parallel_constraint"
    bl_label = "Add Parallel"
    bl_description = "Add a parallel constraint to two selected edges"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        edges = _selected_edges(obj)
        if len(edges) != 2:
            self.report({"WARNING"}, "Select 2 edges")
            return {"CANCELLED"}

        constraint = ParallelConstraint(
            id=new_constraint_id(),
            line_a=str(edges[0].index),
            line_b=str(edges[1].index),
        )
        append_constraint(obj, constraint)

        diag = solve_mesh(obj, load_constraints(obj))
        update_dimensions(context, obj, load_constraints(obj))
        _update_solver_report(context, diag)

        self.report({"INFO"}, "Parallel constraint added")
        return {"FINISHED"}


class AIHELPER_OT_add_perpendicular_constraint(bpy.types.Operator):
    bl_idname = "aihelper.add_perpendicular_constraint"
    bl_label = "Add Perpendicular"
    bl_description = "Add a perpendicular constraint to two selected edges"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        edges = _selected_edges(obj)
        if len(edges) != 2:
            self.report({"WARNING"}, "Select 2 edges")
            return {"CANCELLED"}

        constraint = PerpendicularConstraint(
            id=new_constraint_id(),
            line_a=str(edges[0].index),
            line_b=str(edges[1].index),
        )
        append_constraint(obj, constraint)

        diag = solve_mesh(obj, load_constraints(obj))
        update_dimensions(context, obj, load_constraints(obj))
        _update_solver_report(context, diag)

        self.report({"INFO"}, "Perpendicular constraint added")
        return {"FINISHED"}


class AIHELPER_OT_add_fix_constraint(bpy.types.Operator):
    bl_idname = "aihelper.add_fix_constraint"
    bl_label = "Add Fix"
    bl_description = "Lock selected vertex in place"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        verts = _selected_vertices(obj)
        if len(verts) != 1:
            self.report({"WARNING"}, "Select 1 vertex")
            return {"CANCELLED"}

        v = verts[0]
        constraint = FixConstraint(id=new_constraint_id(), point=str(v.index))
        append_constraint(obj, constraint)

        diag = solve_mesh(obj, load_constraints(obj))
        update_dimensions(context, obj, load_constraints(obj))
        _update_solver_report(context, diag)

        self.report({"INFO"}, "Fix constraint added")
        return {"FINISHED"}


class AIHELPER_OT_solve_constraints(bpy.types.Operator):
    bl_idname = "aihelper.solve_constraints"
    bl_label = "Solve Constraints"
    bl_description = "Re-solve constraints for the sketch mesh"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        constraints = load_constraints(obj)
        if not constraints:
            self.report({"WARNING"}, "No constraints to solve")
            return {"CANCELLED"}

        diag = solve_mesh(obj, constraints)
        update_dimensions(context, obj, constraints)
        _update_solver_report(context, diag)

        self.report({"INFO"}, "Constraints solved")
        return {"FINISHED"}


class AIHELPER_OT_clear_constraints(bpy.types.Operator):
    bl_idname = "aihelper.clear_constraints"
    bl_label = "Clear Constraints"
    bl_description = "Remove all constraints from the sketch mesh"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        clear_constraints(obj)
        clear_dimensions(context)
        context.scene.ai_helper.last_solver_report = ""
        context.scene.ai_helper.last_solver_details = ""
        context.scene.ai_helper.last_solver_worst_id = ""
        self.report({"INFO"}, "Constraints cleared")
        return {"FINISHED"}


class AIHELPER_OT_clear_solver_report(bpy.types.Operator):
    bl_idname = "aihelper.clear_solver_report"
    bl_label = "Clear Diagnostics"
    bl_description = "Clear solver diagnostics output"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.ai_helper
        props.last_solver_report = ""
        props.last_solver_details = ""
        props.last_solver_worst_id = ""
        self.report({"INFO"}, "Diagnostics cleared")
        return {"FINISHED"}


class AIHELPER_OT_update_dimensions(bpy.types.Operator):
    bl_idname = "aihelper.update_dimensions"
    bl_label = "Update Dimensions"
    bl_description = "Create or update dimension labels"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        constraints = load_constraints(obj)
        update_dimensions(context, obj, constraints)
        self.report({"INFO"}, "Dimensions updated")
        return {"FINISHED"}


class AIHELPER_OT_clear_dimensions(bpy.types.Operator):
    bl_idname = "aihelper.clear_dimensions"
    bl_label = "Clear Dimensions"
    bl_description = "Remove all dimension labels"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        clear_dimensions(context)
        self.report({"INFO"}, "Dimensions cleared")
        return {"FINISHED"}


class AIHELPER_OT_edit_distance_constraint(bpy.types.Operator):
    bl_idname = "aihelper.edit_distance_constraint"
    bl_label = "Edit Distance"
    bl_description = "Edit a distance constraint value"
    bl_options = {"REGISTER", "UNDO"}

    constraint_id: bpy.props.StringProperty()
    distance: bpy.props.FloatProperty(
        name="Distance",
        description="Target distance",
        min=0.0,
        default=1.0,
    )

    def invoke(self, context, _event):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        constraints = load_constraints(obj)
        for constraint in constraints:
            if getattr(constraint, "id", None) == self.constraint_id and isinstance(constraint, DistanceConstraint):
                self.distance = constraint.distance
                break
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        def updater(constraint):
            if isinstance(constraint, DistanceConstraint):
                return DistanceConstraint(
                    id=constraint.id,
                    p1=constraint.p1,
                    p2=constraint.p2,
                    distance=self.distance,
                )
            return constraint

        if not update_constraint(obj, self.constraint_id, updater):
            self.report({"WARNING"}, "Constraint not found")
            return {"CANCELLED"}

        diag = solve_mesh(obj, load_constraints(obj))
        update_dimensions(context, obj, load_constraints(obj))
        _update_solver_report(context, diag)

        self.report({"INFO"}, "Distance updated")
        return {"FINISHED"}


class AIHELPER_OT_edit_angle_constraint(bpy.types.Operator):
    bl_idname = "aihelper.edit_angle_constraint"
    bl_label = "Edit Angle"
    bl_description = "Edit an angle constraint value"
    bl_options = {"REGISTER", "UNDO"}

    constraint_id: bpy.props.StringProperty()
    degrees: bpy.props.FloatProperty(
        name="Angle",
        description="Target angle in degrees",
        min=0.0,
        max=180.0,
        default=90.0,
    )

    def invoke(self, context, _event):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        constraints = load_constraints(obj)
        for constraint in constraints:
            if getattr(constraint, "id", None) == self.constraint_id and isinstance(constraint, AngleConstraint):
                self.degrees = constraint.degrees
                break
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        def updater(constraint):
            if isinstance(constraint, AngleConstraint):
                return AngleConstraint(
                    id=constraint.id,
                    p1=constraint.p1,
                    vertex=constraint.vertex,
                    p2=constraint.p2,
                    degrees=self.degrees,
                )
            return constraint

        if not update_constraint(obj, self.constraint_id, updater):
            self.report({"WARNING"}, "Constraint not found")
            return {"CANCELLED"}

        diag = solve_mesh(obj, load_constraints(obj))
        update_dimensions(context, obj, load_constraints(obj))
        _update_solver_report(context, diag)

        self.report({"INFO"}, "Angle updated")
        return {"FINISHED"}


class AIHELPER_OT_edit_radius_constraint(bpy.types.Operator):
    bl_idname = "aihelper.edit_radius_constraint"
    bl_label = "Edit Radius"
    bl_description = "Edit a radius constraint value"
    bl_options = {"REGISTER", "UNDO"}

    constraint_id: bpy.props.StringProperty()
    radius: bpy.props.FloatProperty(
        name="Radius",
        description="Target radius",
        min=0.0,
        default=1.0,
    )

    def invoke(self, context, _event):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        constraints = load_constraints(obj)
        for constraint in constraints:
            if getattr(constraint, "id", None) == self.constraint_id and isinstance(constraint, RadiusConstraint):
                self.radius = constraint.radius
                break
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        def updater(constraint):
            if isinstance(constraint, RadiusConstraint):
                update_circle_radius(obj, constraint.entity, self.radius)
                return RadiusConstraint(
                    id=constraint.id,
                    entity=constraint.entity,
                    radius=self.radius,
                )
            return constraint

        if not update_constraint(obj, self.constraint_id, updater):
            self.report({"WARNING"}, "Constraint not found")
            return {"CANCELLED"}

        diag = solve_mesh(obj, load_constraints(obj))
        update_dimensions(context, obj, load_constraints(obj))
        _update_solver_report(context, diag)

        self.report({"INFO"}, "Radius updated")
        return {"FINISHED"}


class AIHELPER_OT_remove_constraint(bpy.types.Operator):
    bl_idname = "aihelper.remove_constraint"
    bl_label = "Remove Constraint"
    bl_description = "Remove a constraint"
    bl_options = {"REGISTER", "UNDO"}

    constraint_id: bpy.props.StringProperty()

    def execute(self, context):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        if not remove_constraint(obj, self.constraint_id):
            self.report({"WARNING"}, "Constraint not found")
            return {"CANCELLED"}

        diag = solve_mesh(obj, load_constraints(obj))
        update_dimensions(context, obj, load_constraints(obj))
        _update_solver_report(context, diag)
        self.report({"INFO"}, "Constraint removed")
        return {"FINISHED"}


class AIHELPER_OT_edit_selected_dimension(bpy.types.Operator):
    bl_idname = "aihelper.edit_selected_dimension"
    bl_label = "Edit Selected Dimension"
    bl_description = "Edit the constraint value for the selected label"
    bl_options = {"REGISTER", "UNDO"}

    distance: bpy.props.FloatProperty(
        name="Distance",
        description="Target distance",
        min=0.0,
        default=1.0,
    )
    degrees: bpy.props.FloatProperty(
        name="Angle",
        description="Target angle in degrees",
        min=0.0,
        max=180.0,
        default=90.0,
    )
    radius: bpy.props.FloatProperty(
        name="Radius",
        description="Target radius",
        min=0.0,
        default=1.0,
    )
    constraint_id: bpy.props.StringProperty()
    kind: bpy.props.StringProperty()

    def draw(self, _context):
        layout = self.layout
        if self.kind == "angle":
            layout.prop(self, "degrees")
        elif self.kind == "radius":
            layout.prop(self, "radius")
        else:
            layout.prop(self, "distance")

    def invoke(self, context, _event):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        label = context.active_object
        if label is None:
            self.report({"WARNING"}, "Select a dimension label")
            return {"CANCELLED"}

        constraint_id = get_dimension_constraint_id(label)
        if not constraint_id:
            self.report({"WARNING"}, "Active object is not a dimension label")
            return {"CANCELLED"}

        kind = get_dimension_kind(label) or "distance"
        constraints = load_constraints(obj)
        for constraint in constraints:
            if getattr(constraint, "id", None) != constraint_id:
                continue
            if kind == "angle" and isinstance(constraint, AngleConstraint):
                self.degrees = constraint.degrees
                break
            if kind == "radius" and isinstance(constraint, RadiusConstraint):
                self.radius = constraint.radius
                break
            if kind == "distance" and isinstance(constraint, DistanceConstraint):
                self.distance = constraint.distance
                break
        else:
            self.report({"WARNING"}, "Constraint not found")
            return {"CANCELLED"}

        self.constraint_id = constraint_id
        self.kind = kind
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        constraint_id = getattr(self, "constraint_id", None)
        if not constraint_id:
            self.report({"WARNING"}, "No constraint selected")
            return {"CANCELLED"}

        def updater(constraint):
            if constraint.id != constraint_id:
                return constraint
            if self.kind == "angle" and isinstance(constraint, AngleConstraint):
                return AngleConstraint(
                    id=constraint.id,
                    p1=constraint.p1,
                    vertex=constraint.vertex,
                    p2=constraint.p2,
                    degrees=self.degrees,
                )
            if self.kind == "radius" and isinstance(constraint, RadiusConstraint):
                update_circle_radius(obj, constraint.entity, self.radius)
                return RadiusConstraint(
                    id=constraint.id,
                    entity=constraint.entity,
                    radius=self.radius,
                )
            if self.kind == "distance" and isinstance(constraint, DistanceConstraint):
                return DistanceConstraint(
                    id=constraint.id,
                    p1=constraint.p1,
                    p2=constraint.p2,
                    distance=self.distance,
                )
            return constraint

        if not update_constraint(obj, constraint_id, updater):
            self.report({"WARNING"}, "Constraint not found")
            return {"CANCELLED"}

        diag = solve_mesh(obj, load_constraints(obj))
        update_dimensions(context, obj, load_constraints(obj))
        _update_solver_report(context, diag)
        self.report({"INFO"}, "Dimension updated")
        return {"FINISHED"}


class AIHELPER_OT_select_constraint(bpy.types.Operator):
    bl_idname = "aihelper.select_constraint"
    bl_label = "Select Constraint"
    bl_description = "Select geometry associated with a constraint"
    bl_options = {"REGISTER", "UNDO"}

    constraint_id: bpy.props.StringProperty()
    extend: bpy.props.BoolProperty(default=False, options={"HIDDEN"})

    def invoke(self, context, event):
        self.extend = bool(event.shift)
        return self.execute(context)

    def execute(self, context):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        constraint_id = getattr(self, "constraint_id", None)
        if not constraint_id:
            self.report({"WARNING"}, "No constraint selected")
            return {"CANCELLED"}

        constraints = load_constraints(obj)
        target = None
        for constraint in constraints:
            if getattr(constraint, "id", None) == constraint_id:
                target = constraint
                break
        if target is None:
            self.report({"WARNING"}, "Constraint not found")
            return {"CANCELLED"}

        context.view_layer.objects.active = obj
        ok, message = _select_constraint_geometry(obj, target, extend=self.extend)
        if not ok:
            self.report({"WARNING"}, message)
            return {"CANCELLED"}
        return {"FINISHED"}


class AIHELPER_OT_select_worst_constraint(bpy.types.Operator):
    bl_idname = "aihelper.select_worst_constraint"
    bl_label = "Select Worst"
    bl_description = "Select geometry for the worst constraint error"
    bl_options = {"REGISTER", "UNDO"}

    extend: bpy.props.BoolProperty(default=False, options={"HIDDEN"})

    def invoke(self, context, event):
        self.extend = bool(event.shift)
        return self.execute(context)

    def execute(self, context):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        constraint_id = context.scene.ai_helper.last_solver_worst_id
        if not constraint_id:
            self.report({"WARNING"}, "No solver diagnostics available")
            return {"CANCELLED"}

        constraints = load_constraints(obj)
        target = None
        for constraint in constraints:
            if getattr(constraint, "id", None) == constraint_id:
                target = constraint
                break
        if target is None:
            self.report({"WARNING"}, "Worst constraint not found")
            return {"CANCELLED"}

        context.view_layer.objects.active = obj
        ok, message = _select_constraint_geometry(obj, target, extend=self.extend)
        if not ok:
            self.report({"WARNING"}, message)
            return {"CANCELLED"}
        return {"FINISHED"}


def register():
    bpy.utils.register_class(AIHELPER_OT_add_distance_constraint)
    bpy.utils.register_class(AIHELPER_OT_add_horizontal_constraint)
    bpy.utils.register_class(AIHELPER_OT_add_vertical_constraint)
    bpy.utils.register_class(AIHELPER_OT_add_angle_constraint)
    bpy.utils.register_class(AIHELPER_OT_add_radius_constraint)
    bpy.utils.register_class(AIHELPER_OT_add_coincident_constraint)
    bpy.utils.register_class(AIHELPER_OT_add_midpoint_constraint)
    bpy.utils.register_class(AIHELPER_OT_add_equal_length_constraint)
    bpy.utils.register_class(AIHELPER_OT_add_concentric_constraint)
    bpy.utils.register_class(AIHELPER_OT_add_symmetry_constraint)
    bpy.utils.register_class(AIHELPER_OT_add_parallel_constraint)
    bpy.utils.register_class(AIHELPER_OT_add_perpendicular_constraint)
    bpy.utils.register_class(AIHELPER_OT_add_fix_constraint)
    bpy.utils.register_class(AIHELPER_OT_solve_constraints)
    bpy.utils.register_class(AIHELPER_OT_clear_constraints)
    bpy.utils.register_class(AIHELPER_OT_clear_solver_report)
    bpy.utils.register_class(AIHELPER_OT_edit_distance_constraint)
    bpy.utils.register_class(AIHELPER_OT_edit_angle_constraint)
    bpy.utils.register_class(AIHELPER_OT_edit_radius_constraint)
    bpy.utils.register_class(AIHELPER_OT_remove_constraint)
    bpy.utils.register_class(AIHELPER_OT_update_dimensions)
    bpy.utils.register_class(AIHELPER_OT_clear_dimensions)
    bpy.utils.register_class(AIHELPER_OT_edit_selected_dimension)
    bpy.utils.register_class(AIHELPER_OT_select_constraint)
    bpy.utils.register_class(AIHELPER_OT_select_worst_constraint)


def unregister():
    bpy.utils.unregister_class(AIHELPER_OT_select_worst_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_select_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_edit_selected_dimension)
    bpy.utils.unregister_class(AIHELPER_OT_clear_dimensions)
    bpy.utils.unregister_class(AIHELPER_OT_update_dimensions)
    bpy.utils.unregister_class(AIHELPER_OT_remove_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_edit_radius_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_edit_angle_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_edit_distance_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_clear_solver_report)
    bpy.utils.unregister_class(AIHELPER_OT_clear_constraints)
    bpy.utils.unregister_class(AIHELPER_OT_solve_constraints)
    bpy.utils.unregister_class(AIHELPER_OT_add_fix_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_add_vertical_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_add_horizontal_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_add_perpendicular_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_add_parallel_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_add_midpoint_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_add_coincident_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_add_equal_length_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_add_concentric_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_add_symmetry_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_add_radius_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_add_angle_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_add_distance_constraint)
