import bpy
from ..sketch.constraints import (
    DistanceConstraint,
    FixConstraint,
    HorizontalConstraint,
    VerticalConstraint,
)
from ..sketch.dimensions import clear_dimensions, get_dimension_constraint_id, update_distance_dimensions
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


def _selected_vertices(obj):
    return [v for v in obj.data.vertices if v.select]


def _format_diag(diag):
    status = "OK" if diag.converged else "WARN"
    fallback = "yes" if diag.fallback_applied else "no"
    return f"{status} it={diag.iterations} err={diag.max_error:.4f} fallback={fallback}"


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

    def execute(self, context):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        edge = _selected_edge(obj)
        if edge is not None:
            v1 = obj.data.vertices[edge.vertices[0]]
            v2 = obj.data.vertices[edge.vertices[1]]
        else:
            verts = _selected_vertices(obj)
            if len(verts) != 2:
                self.report({"WARNING"}, "Select 1 edge or 2 vertices")
                return {"CANCELLED"}
            v1, v2 = verts

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
        update_distance_dimensions(context, obj, load_constraints(obj))
        context.scene.ai_helper.last_solver_report = _format_diag(diag)

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
        update_distance_dimensions(context, obj, load_constraints(obj))
        context.scene.ai_helper.last_solver_report = _format_diag(diag)

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
        update_distance_dimensions(context, obj, load_constraints(obj))
        context.scene.ai_helper.last_solver_report = _format_diag(diag)

        self.report({"INFO"}, "Vertical constraint added")
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
        update_distance_dimensions(context, obj, load_constraints(obj))
        context.scene.ai_helper.last_solver_report = _format_diag(diag)

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
        update_distance_dimensions(context, obj, constraints)
        context.scene.ai_helper.last_solver_report = _format_diag(diag)

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
        update_distance_dimensions(context, obj, constraints)
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
        update_distance_dimensions(context, obj, load_constraints(obj))
        context.scene.ai_helper.last_solver_report = _format_diag(diag)

        self.report({"INFO"}, "Distance updated")
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
        update_distance_dimensions(context, obj, load_constraints(obj))
        context.scene.ai_helper.last_solver_report = _format_diag(diag)
        self.report({"INFO"}, "Constraint removed")
        return {"FINISHED"}


class AIHELPER_OT_edit_selected_dimension(bpy.types.Operator):
    bl_idname = "aihelper.edit_selected_dimension"
    bl_label = "Edit Selected Dimension"
    bl_description = "Edit the distance constraint for the selected label"
    bl_options = {"REGISTER", "UNDO"}

    distance: bpy.props.FloatProperty(
        name="Distance",
        description="Target distance",
        min=0.0,
        default=1.0,
    )
    constraint_id: bpy.props.StringProperty()

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

        constraints = load_constraints(obj)
        for constraint in constraints:
            if getattr(constraint, "id", None) == constraint_id and isinstance(constraint, DistanceConstraint):
                self.distance = constraint.distance
                break
        else:
            self.report({"WARNING"}, "Constraint not found")
            return {"CANCELLED"}

        self.constraint_id = constraint_id
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
            if isinstance(constraint, DistanceConstraint) and constraint.id == constraint_id:
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
        update_distance_dimensions(context, obj, load_constraints(obj))
        context.scene.ai_helper.last_solver_report = _format_diag(diag)
        self.report({"INFO"}, "Dimension updated")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(AIHELPER_OT_add_distance_constraint)
    bpy.utils.register_class(AIHELPER_OT_add_horizontal_constraint)
    bpy.utils.register_class(AIHELPER_OT_add_vertical_constraint)
    bpy.utils.register_class(AIHELPER_OT_add_fix_constraint)
    bpy.utils.register_class(AIHELPER_OT_solve_constraints)
    bpy.utils.register_class(AIHELPER_OT_clear_constraints)
    bpy.utils.register_class(AIHELPER_OT_edit_distance_constraint)
    bpy.utils.register_class(AIHELPER_OT_remove_constraint)
    bpy.utils.register_class(AIHELPER_OT_update_dimensions)
    bpy.utils.register_class(AIHELPER_OT_clear_dimensions)
    bpy.utils.register_class(AIHELPER_OT_edit_selected_dimension)


def unregister():
    bpy.utils.unregister_class(AIHELPER_OT_edit_selected_dimension)
    bpy.utils.unregister_class(AIHELPER_OT_clear_dimensions)
    bpy.utils.unregister_class(AIHELPER_OT_update_dimensions)
    bpy.utils.unregister_class(AIHELPER_OT_remove_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_edit_distance_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_clear_constraints)
    bpy.utils.unregister_class(AIHELPER_OT_solve_constraints)
    bpy.utils.unregister_class(AIHELPER_OT_add_fix_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_add_vertical_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_add_horizontal_constraint)
    bpy.utils.unregister_class(AIHELPER_OT_add_distance_constraint)
