import math

import bpy
from mathutils import Vector

from .llm.recipes import recipe_description
from .sketch.circles import find_circle_by_center, find_circle_by_vertex, load_circles
from .sketch.constraints import AngleConstraint, DistanceConstraint, RadiusConstraint
from .sketch.history import load_history
from .sketch.rectangles import load_rectangles
from .sketch.store import load_constraints
from .sketch.tags import load_tags


def _selected_arc(obj):
    circles = load_circles(obj)
    if not circles:
        return None

    for vert in obj.data.vertices:
        if not vert.select:
            continue
        circle = find_circle_by_vertex(circles, str(vert.index))
        if circle and circle.get("is_arc"):
            return circle
        circle = find_circle_by_center(circles, str(vert.index))
        if circle and circle.get("is_arc"):
            return circle

    for edge in obj.data.edges:
        if not edge.select:
            continue
        for vid in edge.vertices:
            circle = find_circle_by_vertex(circles, str(vid))
            if circle and circle.get("is_arc"):
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


def _rectangle_metrics(obj, rect):
    vert_ids = [int(v) for v in rect.get("verts", [])]
    coords = []
    for vid in vert_ids[:4]:
        try:
            coords.append(obj.data.vertices[vid].co.copy())
        except IndexError:
            coords = []
            break

    if len(coords) == 4:
        center = sum((v for v in coords), Vector()) / len(coords)
        edges = [coords[(i + 1) % 4] - coords[i] for i in range(4)]
        lengths = [edge.length for edge in edges]
        width = max(lengths) if lengths else 0.0
        height = min(lengths) if lengths else 0.0
        rotation = 0.0
        if lengths:
            idx = lengths.index(width)
            vec = edges[idx]
            rotation = math.degrees(math.atan2(vec.y, vec.x)) % 360.0
        return center.x, center.y, width, height, rotation

    center = rect.get("center", [0.0, 0.0])
    try:
        cx, cy = float(center[0]), float(center[1])
    except (TypeError, ValueError, IndexError):
        cx, cy = 0.0, 0.0
    return (
        cx,
        cy,
        float(rect.get("width", 0.0)),
        float(rect.get("height", 0.0)),
        float(rect.get("rotation", 0.0)),
    )


def _inspect_selection(obj):
    arc = _selected_arc(obj)
    if arc:
        return "ARC", f"ARC:{arc.get('id', '')}", arc
    rect = _selected_rectangle(obj)
    if rect:
        return "RECT", f"RECT:{rect.get('id', '')}", rect

    verts = [v for v in obj.data.vertices if v.select]
    if len(verts) == 1:
        return "VERTEX", f"VERTEX:{verts[0].index}", verts[0]
    edges = [e for e in obj.data.edges if e.select]
    if len(edges) == 1:
        return "EDGE", f"EDGE:{edges[0].index}", edges[0]
    return "NONE", "NONE", None


def _update_inspector_props(props, obj):
    kind, key, data = _inspect_selection(obj)
    if key == props.inspector_selection_key:
        return kind
    props.inspector_selection_key = key

    if kind == "VERTEX":
        props.inspector_vertex_x = data.co.x
        props.inspector_vertex_y = data.co.y
    elif kind == "EDGE":
        v1 = obj.data.vertices[data.vertices[0]].co
        v2 = obj.data.vertices[data.vertices[1]].co
        vec = v2 - v1
        props.inspector_edge_length = vec.length
        props.inspector_edge_angle = (math.degrees(math.atan2(vec.y, vec.x)) + 360.0) % 360.0
    elif kind == "ARC":
        center_id = data.get("center")
        center = None
        if center_id is not None:
            try:
                center = obj.data.vertices[int(center_id)].co
                props.inspector_arc_center_x = center.x
                props.inspector_arc_center_y = center.y
            except (ValueError, TypeError, IndexError):
                center = None
        radius = float(data.get("radius", 0.0))
        if radius <= 0.0 and center is not None:
            vert_ids = [int(v) for v in data.get("verts", [])]
            if vert_ids:
                try:
                    vert = obj.data.vertices[vert_ids[0]].co
                    radius = (vert - center).length
                except (ValueError, TypeError, IndexError):
                    radius = 0.0
        props.inspector_arc_radius = radius
        props.inspector_arc_clockwise = bool(data.get("clockwise", False))
        start_angle = data.get("start_angle")
        end_angle = data.get("end_angle")
        if start_angle is None or end_angle is None:
            angles = _arc_angles_for_circle(obj, data)
            if angles:
                start_angle, end_angle = angles
        if start_angle is not None:
            props.inspector_arc_start_angle = float(start_angle)
        if end_angle is not None:
            props.inspector_arc_end_angle = float(end_angle)
    elif kind == "RECT":
        cx, cy, width, height, rotation = _rectangle_metrics(obj, data)
        props.inspector_rect_center_x = cx
        props.inspector_rect_center_y = cy
        props.inspector_rect_width = width
        props.inspector_rect_height = height
        props.inspector_rect_rotation = rotation
    return kind


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
        layout.label(text="Image (optional)")
        layout.prop(props, "image_path", text="")
        layout.prop(props, "image_url", text="URL")
        layout.prop(props, "image_notes", text="Notes")
        layout.label(text="Preset")
        row = layout.row(align=True)
        row.prop(props, "prompt_preset", text="")
        row.operator("aihelper.apply_prompt_preset", text="Use")
        row.operator("aihelper.apply_param_preset", text="Params")
        row = layout.row(align=True)
        op = row.operator("aihelper.apply_prompt_preset", text="Append")
        op.append = True
        op = row.operator("aihelper.apply_param_preset", text="Params+")
        op.append = True
        layout.label(text="Recipe")
        row = layout.row(align=True)
        row.prop(props, "prompt_recipe", text="")
        row.operator("aihelper.apply_prompt_recipe", text="Use")
        row = layout.row(align=True)
        op = row.operator("aihelper.apply_prompt_recipe", text="Append")
        op.append = True
        description = recipe_description(props.prompt_recipe)
        if description:
            for line in description.splitlines():
                layout.label(text=line)
        row = layout.row(align=True)
        row.operator("aihelper.preview_prompt", text="Preview")
        row.operator("aihelper.apply_tool_calls", text="Apply")
        layout.prop(props, "tool_calls_json", text="Preview")
        layout.separator()
        layout.operator("aihelper.sketch_mode", text="Sketch Mode")
        layout.operator("aihelper.add_line", text="Add Line")
        layout.operator("aihelper.add_circle", text="Add Circle")
        layout.operator("aihelper.add_arc", text="Add Arc")
        layout.operator("aihelper.add_rectangle", text="Add Rectangle")
        layout.operator("aihelper.add_polyline", text="Add Polyline")


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
        layout.operator("aihelper.add_coincident_constraint", text="Add Coincident")
        layout.operator("aihelper.add_midpoint_constraint", text="Add Midpoint")
        layout.operator("aihelper.add_equal_length_constraint", text="Add Equal Length")
        layout.operator("aihelper.add_concentric_constraint", text="Add Concentric")
        layout.operator("aihelper.add_symmetry_constraint", text="Add Symmetry")
        layout.operator("aihelper.add_tangent_constraint", text="Add Tangent")
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
        if props.last_solver_worst_id:
            layout.operator("aihelper.select_worst_constraint", text="Select Worst")
        if props.last_solver_details:
            for line in props.last_solver_details.splitlines():
                layout.label(text=line)
        if props.last_solver_report or props.last_solver_details:
            layout.operator("aihelper.clear_solver_report", text="Clear Diagnostics")


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
        layout.operator("aihelper.loft_profiles", text="Loft Profiles")
        layout.operator("aihelper.sweep_profile", text="Sweep Profile")
        layout.operator("aihelper.rebuild_3d_ops", text="Rebuild 3D Ops")
        layout.separator()
        layout.label(text="Modifiers")
        layout.operator("aihelper.add_shell_modifier", text="Add Shell")
        layout.operator("aihelper.clear_shell_modifier", text="Clear Shell")
        layout.operator("aihelper.add_bevel_modifier", text="Add Fillet")
        layout.operator("aihelper.clear_bevel_modifier", text="Clear Fillet")


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
        layout.prop(props, "angle_snap_enabled")
        col_angle = layout.column()
        col_angle.enabled = props.angle_snap_enabled
        col_angle.prop(props, "angle_snap_deg")
        row = col_angle.row(align=True)
        row.label(text="Presets")
        for value in (15.0, 30.0, 45.0):
            op = row.operator("aihelper.set_angle_snap_preset", text=f"{int(value)}")
            op.angle = value
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
        layout.operator("aihelper.set_edge_length", text="Set Edge Length")
        layout.operator("aihelper.set_edge_angle", text="Set Edge Angle")
        layout.operator("aihelper.edit_arc", text="Edit Arc")
        layout.operator("aihelper.edit_rectangle", text="Edit Rectangle")


class AIHELPER_PT_history(bpy.types.Panel):
    bl_label = "History"
    bl_idname = "AIHELPER_PT_history"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Helper"
    bl_parent_id = "AIHELPER_PT_main"

    def draw(self, context):
        layout = self.layout
        obj = context.scene.objects.get("AI_Sketch")
        if obj is None or obj.type != "MESH":
            layout.label(text="No sketch mesh found")
            return

        history = load_history(obj)
        layout.label(text=f"History: {len(history)}")
        layout.operator("aihelper.capture_snapshot", text="Capture Snapshot")
        layout.operator("aihelper.clear_history", text="Clear History")
        if history:
            layout.separator()
            start = max(len(history) - 10, 0)
            for idx, entry in enumerate(history[start:], start=start):
                label = entry.get("label", "Snapshot")
                row = layout.row(align=True)
                row.label(text=label)
                op = row.operator("aihelper.restore_snapshot", text="Restore")
                op.index = idx


class AIHELPER_PT_inspector(bpy.types.Panel):
    bl_label = "Inspector"
    bl_idname = "AIHELPER_PT_inspector"
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

        kind = _update_inspector_props(props, obj)
        if kind == "VERTEX":
            layout.prop(props, "inspector_vertex_x", text="X")
            layout.prop(props, "inspector_vertex_y", text="Y")
            layout.operator("aihelper.inspector_apply_vertex", text="Apply")
        elif kind == "EDGE":
            layout.prop(props, "inspector_edge_length", text="Length")
            layout.prop(props, "inspector_edge_angle", text="Angle")
            layout.prop(props, "inspector_edge_anchor", text="Anchor")
            row = layout.row(align=True)
            row.operator("aihelper.inspector_apply_edge_length", text="Apply Length")
            row.operator("aihelper.inspector_apply_edge_angle", text="Apply Angle")
        elif kind == "ARC":
            layout.prop(props, "inspector_arc_center_x", text="Center X")
            layout.prop(props, "inspector_arc_center_y", text="Center Y")
            layout.prop(props, "inspector_arc_radius", text="Radius")
            layout.prop(props, "inspector_arc_start_angle", text="Start")
            layout.prop(props, "inspector_arc_end_angle", text="End")
            layout.prop(props, "inspector_arc_clockwise", text="Clockwise")
            layout.operator("aihelper.inspector_apply_arc", text="Apply Arc")
        elif kind == "RECT":
            layout.prop(props, "inspector_rect_center_x", text="Center X")
            layout.prop(props, "inspector_rect_center_y", text="Center Y")
            layout.prop(props, "inspector_rect_width", text="Width")
            layout.prop(props, "inspector_rect_height", text="Height")
            layout.prop(props, "inspector_rect_rotation", text="Rotation")
            layout.operator("aihelper.inspector_apply_rectangle", text="Apply Rectangle")
        else:
            layout.label(text="Select 1 vertex/edge, arc, or rectangle.")


class AIHELPER_PT_tags(bpy.types.Panel):
    bl_label = "Tags"
    bl_idname = "AIHELPER_PT_tags"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Helper"
    bl_parent_id = "AIHELPER_PT_main"

    def draw(self, context):
        layout = self.layout
        obj = context.scene.objects.get("AI_Sketch")
        if obj is None or obj.type != "MESH":
            layout.label(text="No sketch mesh found")
            return

        tags = load_tags(obj)
        if not tags:
            layout.label(text="No tags found")
            return

        for tag in sorted(tags.keys()):
            row = layout.row(align=True)
            row.label(text=tag)
            op = row.operator("aihelper.select_tag", text="Select")
            op.tag = tag
            op = row.operator("aihelper.select_tag", text="Add")
            op.tag = tag
            op.extend = True


def register():
    bpy.utils.register_class(AIHELPER_PT_main)
    bpy.utils.register_class(AIHELPER_PT_constraints)
    bpy.utils.register_class(AIHELPER_PT_ops3d)
    bpy.utils.register_class(AIHELPER_PT_sketch)
    bpy.utils.register_class(AIHELPER_PT_history)
    bpy.utils.register_class(AIHELPER_PT_inspector)
    bpy.utils.register_class(AIHELPER_PT_tags)


def unregister():
    bpy.utils.unregister_class(AIHELPER_PT_tags)
    bpy.utils.unregister_class(AIHELPER_PT_inspector)
    bpy.utils.unregister_class(AIHELPER_PT_history)
    bpy.utils.unregister_class(AIHELPER_PT_sketch)
    bpy.utils.unregister_class(AIHELPER_PT_ops3d)
    bpy.utils.unregister_class(AIHELPER_PT_constraints)
    bpy.utils.unregister_class(AIHELPER_PT_main)
