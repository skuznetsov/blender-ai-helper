import math

import bpy
from ..sketch.constraints import (
    AngleConstraint,
    DistanceConstraint,
    FixConstraint,
    HorizontalConstraint,
    ParallelConstraint,
    PerpendicularConstraint,
    RadiusConstraint,
    VerticalConstraint,
)
from ..sketch.circles import find_circle_by_vertex, load_circles, update_circle_radius
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

    for edge in obj.data.edges:
        if not edge.select:
            continue
        for vid in edge.vertices:
            circle = find_circle_by_vertex(circles, str(vid))
            if circle:
                return circle
    return None


def _format_diag(diag):
    status = "OK" if diag.converged else "WARN"
    fallback = "yes" if diag.fallback_applied else "no"
    return f"{status} it={diag.iterations} err={diag.max_error:.4f} fallback={fallback}"


def _format_diag_details(diag):
    lines = []
    for entry in diag.worst_constraints:
        cid = entry.constraint_id or "?"
        short = cid[:6] if cid != "?" else cid
        lines.append(f"{entry.kind} {short} err={entry.error:.4f}")
    return "\n".join(lines)


def _update_solver_report(context, diag):
    props = context.scene.ai_helper
    props.last_solver_report = _format_diag(diag)
    props.last_solver_details = _format_diag_details(diag)


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
        self.report({"INFO"}, "Constraints cleared")
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


def register():
    bpy.utils.register_class(AIHELPER_OT_add_distance_constraint)
    bpy.utils.register_class(AIHELPER_OT_add_horizontal_constraint)
    bpy.utils.register_class(AIHELPER_OT_add_vertical_constraint)
    bpy.utils.register_class(AIHELPER_OT_add_angle_constraint)
    bpy.utils.register_class(AIHELPER_OT_add_radius_constraint)
    bpy.utils.register_class(AIHELPER_OT_add_parallel_constraint)
    bpy.utils.register_class(AIHELPER_OT_add_perpendicular_constraint)
    bpy.utils.register_class(AIHELPER_OT_add_fix_constraint)
    bpy.utils.register_class(AIHELPER_OT_solve_constraints)
    bpy.utils.register_class(AIHELPER_OT_clear_constraints)
    bpy.utils.register_class(AIHELPER_OT_edit_distance_constraint)
    bpy.utils.register_class(AIHELPER_OT_edit_angle_constraint)
    bpy.utils.register_class(AIHELPER_OT_edit_radius_constraint)
    bpy.utils.register_class(AIHELPER_OT_remove_constraint)
    bpy.utils.register_class(AIHELPER_OT_update_dimensions)
    bpy.utils.register_class(AIHELPER_OT_clear_dimensions)
    bpy.utils.register_class(AIHELPER_OT_edit_selected_dimension)


def unregister():
    bpy.utils.unregister_class(AIHELPER_OT_edit_selected_dimension)
    bpy.utils.unregister_class(AIHELPER_OT_clear_dimensions)
    bpy.utils.unregister_class(AIHELPER_OT_update_dimensions)
    bpy.utils.unregister_class(AIHELPER_OT_remove_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_edit_radius_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_edit_angle_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_edit_distance_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_clear_constraints)
    bpy.utils.unregister_class(AIHELPER_OT_solve_constraints)
    bpy.utils.unregister_class(AIHELPER_OT_add_fix_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_add_vertical_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_add_horizontal_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_add_perpendicular_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_add_parallel_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_add_radius_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_add_angle_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_add_distance_constraint)
