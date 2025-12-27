import bpy

from .sketch.constraints import AngleConstraint, DistanceConstraint, RadiusConstraint
from .sketch.store import load_constraints


class AIHELPER_PT_main(bpy.types.Panel):
    bl_label = "AI Helper"
    bl_idname = "AIHELPER_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Helper"

    def draw(self, context):
        layout = self.layout
        props = context.scene.ai_helper

        layout.label(text="Prompt")
        layout.prop(props, "prompt", text="")
        row = layout.row(align=True)
        row.operator("aihelper.preview_prompt", text="Preview")
        row.operator("aihelper.apply_tool_calls", text="Apply")
        layout.prop(props, "tool_calls_json", text="Preview")
        layout.separator()
        layout.operator("aihelper.sketch_mode", text="Sketch Mode")
        layout.operator("aihelper.add_circle", text="Add Circle")


class AIHELPER_PT_constraints(bpy.types.Panel):
    bl_label = "Constraints"
    bl_idname = "AIHELPER_PT_constraints"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Helper"
    bl_parent_id = "AIHELPER_PT_main"

    def draw(self, context):
        layout = self.layout
        props = context.scene.ai_helper
        obj = context.scene.objects.get("AI_Sketch")
        if obj is None or obj.type != "MESH":
            layout.label(text="No sketch mesh found")
            return

        constraints = load_constraints(obj)
        layout.label(text=f"Constraints: {len(constraints)}")
        layout.operator("aihelper.add_distance_constraint", text="Add Distance")
        layout.operator("aihelper.add_horizontal_constraint", text="Add Horizontal")
        layout.operator("aihelper.add_vertical_constraint", text="Add Vertical")
        layout.operator("aihelper.add_angle_constraint", text="Add Angle")
        layout.operator("aihelper.add_radius_constraint", text="Add Radius")
        layout.operator("aihelper.add_parallel_constraint", text="Add Parallel")
        layout.operator("aihelper.add_perpendicular_constraint", text="Add Perpendicular")
        layout.operator("aihelper.add_fix_constraint", text="Add Fix")
        layout.separator()
        layout.operator("aihelper.solve_constraints", text="Solve")
        layout.operator("aihelper.clear_constraints", text="Clear")
        layout.separator()
        layout.operator("aihelper.update_dimensions", text="Update Dimensions")
        layout.operator("aihelper.clear_dimensions", text="Clear Dimensions")
        layout.operator("aihelper.edit_selected_dimension", text="Edit Selected Dimension")
        if constraints:
            layout.separator()
            for constraint in constraints[:10]:
                row = layout.row(align=True)
                label = f"{constraint.kind} {constraint.id[:6]}"
                row.label(text=label)
                op = row.operator("aihelper.select_constraint", text="Sel")
                op.constraint_id = constraint.id
                if isinstance(constraint, DistanceConstraint):
                    op = row.operator("aihelper.edit_distance_constraint", text="Edit")
                    op.constraint_id = constraint.id
                elif isinstance(constraint, AngleConstraint):
                    op = row.operator("aihelper.edit_angle_constraint", text="Edit")
                    op.constraint_id = constraint.id
                elif isinstance(constraint, RadiusConstraint):
                    op = row.operator("aihelper.edit_radius_constraint", text="Edit")
                    op.constraint_id = constraint.id
                op = row.operator("aihelper.remove_constraint", text="X")
                op.constraint_id = constraint.id
        if props.last_solver_report:
            layout.label(text=props.last_solver_report)
        if props.last_solver_details:
            for line in props.last_solver_details.splitlines():
                layout.label(text=line)


class AIHELPER_PT_ops3d(bpy.types.Panel):
    bl_label = "3D Ops"
    bl_idname = "AIHELPER_PT_ops3d"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Helper"
    bl_parent_id = "AIHELPER_PT_main"

    def draw(self, context):
        layout = self.layout
        props = context.scene.ai_helper
        layout.prop(props, "auto_rebuild")
        layout.operator("aihelper.extrude_sketch", text="Extrude Sketch")
        layout.operator("aihelper.revolve_sketch", text="Revolve Sketch")
        layout.operator("aihelper.rebuild_3d_ops", text="Rebuild 3D Ops")


class AIHELPER_PT_sketch(bpy.types.Panel):
    bl_label = "Sketch Settings"
    bl_idname = "AIHELPER_PT_sketch"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Helper"
    bl_parent_id = "AIHELPER_PT_main"

    def draw(self, context):
        layout = self.layout
        props = context.scene.ai_helper
        layout.prop(props, "auto_constraints")
        layout.prop(props, "hv_tolerance_deg")
        layout.separator()
        layout.prop(props, "snap_enabled")
        col = layout.column()
        col.enabled = props.snap_enabled
        col.prop(props, "snap_grid")
        col.prop(props, "snap_verts")
        col.prop(props, "snap_mids")
        col.prop(props, "snap_inters")
        col.prop(props, "snap_radius")
        col.prop(props, "grid_step")
        layout.separator()
        layout.label(text="Precision")
        layout.operator("aihelper.set_vertex_coords", text="Set Vertex Coords")


def register():
    bpy.utils.register_class(AIHELPER_PT_main)
    bpy.utils.register_class(AIHELPER_PT_constraints)
    bpy.utils.register_class(AIHELPER_PT_ops3d)
    bpy.utils.register_class(AIHELPER_PT_sketch)


def unregister():
    bpy.utils.unregister_class(AIHELPER_PT_sketch)
    bpy.utils.unregister_class(AIHELPER_PT_ops3d)
    bpy.utils.unregister_class(AIHELPER_PT_constraints)
    bpy.utils.unregister_class(AIHELPER_PT_main)
