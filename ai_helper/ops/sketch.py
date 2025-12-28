import math

import bpy
import bmesh
from bpy_extras import view3d_utils
from mathutils import Matrix, Vector

from ..sketch.constraints import HorizontalConstraint, VerticalConstraint
from ..sketch.circles import append_circle, new_circle_id
from ..sketch.dimensions import update_dimensions
from ..sketch.history import snapshot_state
from ..sketch.quadtree import Point2D, Quadtree
from ..sketch.solver_bridge import solve_mesh
from ..sketch.store import append_constraint, load_constraints, new_constraint_id


def ensure_sketch_object(context):
    name = "AI_Sketch"
    obj = context.scene.objects.get(name)
    if obj is not None:
        if obj.type != "MESH":
            return None
        return obj

    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    context.collection.objects.link(obj)
    return obj


def _selected_vertices(obj):
    return [v for v in obj.data.vertices if v.select]


def _selected_edges(obj):
    return [e for e in obj.data.edges if e.select]


def parse_polar(text, start):
    if start is None:
        return None
    if text.startswith("@"):
        text = text[1:]
    if "<" not in text:
        return None

    length_str, angle_str = [p.strip() for p in text.split("<", 1)]
    try:
        length = float(length_str)
        angle = float(angle_str)
    except ValueError:
        return None

    radians = math.radians(angle)
    dx = length * math.cos(radians)
    dy = length * math.sin(radians)
    return Vector((start.x + dx, start.y + dy, 0.0))


def parse_input(text, start, relative_mode):
    text = text.strip()
    if not text:
        return None

    if text.startswith("@"):
        return parse_polar(text, start)

    absolute = False
    if text.startswith("="):
        absolute = True
        text = text[1:]

    if "," not in text:
        return None

    parts = [p.strip() for p in text.split(",", 1)]
    if len(parts) != 2:
        return None

    try:
        x = float(parts[0])
        y = float(parts[1])
    except ValueError:
        return None

    if absolute or not relative_mode:
        return Vector((x, y, 0.0))
    if start is None:
        return None
    return Vector((start.x + x, start.y + y, 0.0))


def apply_axis_lock(location, start, axis_lock):
    if start is None or axis_lock is None:
        return location
    if axis_lock == "X":
        return Vector((location.x, start.y, 0.0))
    if axis_lock == "Y":
        return Vector((start.x, location.y, 0.0))
    return location


def apply_angle_snap(location, start, angle_snap_enabled, angle_snap_deg, axis_lock):
    if start is None or not angle_snap_enabled or axis_lock is not None:
        return location
    if angle_snap_deg <= 0.0:
        return location

    dx = location.x - start.x
    dy = location.y - start.y
    length = math.hypot(dx, dy)
    if length < 1e-8:
        return location

    step = math.radians(angle_snap_deg)
    angle = math.atan2(dy, dx)
    snapped = round(angle / step) * step
    return Vector(
        (
            start.x + math.cos(snapped) * length,
            start.y + math.sin(snapped) * length,
            0.0,
        )
    )


def format_preview(start, point):
    if start is None or point is None:
        return ""
    dx = point.x - start.x
    dy = point.y - start.y
    length = math.hypot(dx, dy)
    angle = (math.degrees(math.atan2(dy, dx)) + 360.0) % 360.0
    return f"len={length:.3f} ang={angle:.1f}"


def grid_step_value(grid_step, scale_length):
    scale = scale_length or 1.0
    return grid_step * scale


def snap_to_grid(location, grid_step, scale_length, snap_grid):
    if not snap_grid:
        return location

    step = grid_step_value(grid_step, scale_length)
    if step <= 0.0:
        return location

    x = math.floor(location.x / step + 0.5) * step
    y = math.floor(location.y / step + 0.5) * step
    return Vector((x, y, 0.0))


def point_on_segment(px, py, x1, y1, x2, y2):
    min_x = min(x1, x2) - 1e-6
    max_x = max(x1, x2) + 1e-6
    min_y = min(y1, y2) - 1e-6
    max_y = max(y1, y2) + 1e-6
    return min_x <= px <= max_x and min_y <= py <= max_y


def segment_intersection(p1, p2, p3, p4):
    x1, y1 = p1.x, p1.y
    x2, y2 = p2.x, p2.y
    x3, y3 = p3.x, p3.y
    x4, y4 = p4.x, p4.y

    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-8:
        return None

    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / denom
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / denom

    if not point_on_segment(px, py, x1, y1, x2, y2):
        return None
    if not point_on_segment(px, py, x3, y3, x4, y4):
        return None

    return Vector((px, py, 0.0))


def segment_intersections(segments):
    hits = []
    count = len(segments)
    for i in range(count):
        a1, a2, a_idx1, a_idx2 = segments[i]
        for j in range(i + 1, count):
            b1, b2, b_idx1, b_idx2 = segments[j]
            if a_idx1 in (b_idx1, b_idx2) or a_idx2 in (b_idx1, b_idx2):
                continue
            hit = segment_intersection(a1, a2, b1, b2)
            if hit is not None:
                hits.append(Point2D(hit.x, hit.y, payload=("inter", i, j)))
    return hits


def collect_feature_points(obj, snap_verts, snap_mids, snap_inters):
    if obj is None or obj.type != "MESH":
        return []

    verts = obj.data.vertices
    points = []
    segments = []

    for v in verts:
        pos = obj.matrix_world @ v.co
        if snap_verts:
            points.append(Point2D(pos.x, pos.y, payload=("vert", v.index)))

    for edge in obj.data.edges:
        v1 = verts[edge.vertices[0]]
        v2 = verts[edge.vertices[1]]
        p1 = obj.matrix_world @ v1.co
        p2 = obj.matrix_world @ v2.co
        segments.append((p1, p2, v1.index, v2.index))

        if snap_mids:
            mid = (p1 + p2) * 0.5
            points.append(Point2D(mid.x, mid.y, payload=("mid", edge.index)))

    if snap_inters and len(segments) > 1:
        points.extend(segment_intersections(segments))

    return points


def snap_to_features(location, obj, snap_radius, scale_length, snap_verts, snap_mids, snap_inters):
    points = collect_feature_points(obj, snap_verts, snap_mids, snap_inters)
    if not points:
        return None

    tree = Quadtree.build(points)
    nearest = tree.query_nearest(Point2D(location.x, location.y), k=1)
    if not nearest:
        return None

    radius = snap_radius * (scale_length or 1.0)
    candidate = nearest[0]
    if candidate.distance_to(Point2D(location.x, location.y)) <= radius:
        return Vector((candidate.x, candidate.y, 0.0))

    return None


class AIHELPER_OT_sketch_mode(bpy.types.Operator):
    bl_idname = "aihelper.sketch_mode"
    bl_label = "Sketch Mode"
    bl_description = "Enter sketch mode"
    bl_options = {"REGISTER", "UNDO"}

    def __init__(self):
        self.start = None
        self.input_str = ""
        self.relative_mode = True
        self.axis_lock = None
        self.preview_str = ""
        self.angle_snap_enabled = False
        self.angle_snap_deg = 15.0
        self.snap_enabled = True
        self.snap_grid = True
        self.snap_verts = True
        self.snap_mids = True
        self.snap_inters = True
        self.snap_radius = 0.25
        self.grid_step = 1.0
        self.auto_constraints = True
        self.hv_tolerance_deg = 8.0

    def invoke(self, context, event):
        if context.area.type != "VIEW_3D":
            self.report({"WARNING"}, "Sketch Mode requires a 3D View")
            return {"CANCELLED"}

        self.start = None
        self.input_str = ""
        self.relative_mode = True
        self.axis_lock = None
        self.preview_str = ""
        props = context.scene.ai_helper
        self.auto_constraints = props.auto_constraints
        self.hv_tolerance_deg = props.hv_tolerance_deg
        self.snap_enabled = props.snap_enabled
        self.snap_grid = props.snap_grid
        self.snap_verts = props.snap_verts
        self.snap_mids = props.snap_mids
        self.snap_inters = props.snap_inters
        self.angle_snap_enabled = props.angle_snap_enabled
        self.angle_snap_deg = props.angle_snap_deg
        self.snap_radius = props.snap_radius
        self.grid_step = props.grid_step
        context.window_manager.modal_handler_add(self)
        self._set_header(context)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type in {"RIGHTMOUSE", "ESC"}:
            self._clear_header(context)
            return {"CANCELLED"}

        if event.type == "TAB" and event.value == "PRESS":
            self.relative_mode = not self.relative_mode
            self._set_header(context)
            return {"RUNNING_MODAL"}

        if event.type == "A" and event.value == "PRESS":
            self.auto_constraints = not self.auto_constraints
            context.scene.ai_helper.auto_constraints = self.auto_constraints
            self._set_header(context)
            return {"RUNNING_MODAL"}

        if event.type == "Q" and event.value == "PRESS":
            self.angle_snap_enabled = not self.angle_snap_enabled
            context.scene.ai_helper.angle_snap_enabled = self.angle_snap_enabled
            self._set_header(context)
            return {"RUNNING_MODAL"}

        if event.type in {"X", "Y"} and event.value == "PRESS":
            if self.axis_lock == event.type:
                self.axis_lock = None
            else:
                self.axis_lock = event.type
            self._set_header(context)
            return {"RUNNING_MODAL"}

        if event.type == "S" and event.value == "PRESS":
            self.snap_enabled = not self.snap_enabled
            context.scene.ai_helper.snap_enabled = self.snap_enabled
            self._set_header(context)
            return {"RUNNING_MODAL"}

        if event.type == "BACK_SPACE" and event.value == "PRESS":
            self.input_str = self.input_str[:-1]
            self._set_header(context)
            return {"RUNNING_MODAL"}

        if event.type == "MOUSEMOVE":
            self._update_preview(context, event)
            self._set_header(context)
            return {"RUNNING_MODAL"}

        if event.value == "PRESS" and event.ascii:
            if event.ascii in "0123456789-+.,@<=":
                self.input_str += event.ascii
                self._set_header(context)
                return {"RUNNING_MODAL"}

        if event.type == "RET" and event.value == "PRESS":
            if self.start is None:
                self.report({"WARNING"}, "Click to set the start point")
                return {"RUNNING_MODAL"}

            end = self._parse_input(self.input_str)
            if end is None:
                self.report({"WARNING"}, "Invalid input")
                return {"RUNNING_MODAL"}

            edge_id = self._add_line(context, self.start, end)
            if edge_id and self.auto_constraints:
                self._apply_auto_constraints(context, edge_id, self.start, end)
            if edge_id:
                obj = ensure_sketch_object(context)
                if obj is not None:
                    snapshot_state(obj, "Line")
            self.start = end
            self.input_str = ""
            self.preview_str = ""
            self._set_header(context)
            return {"RUNNING_MODAL"}

        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            point = self._mouse_to_plane(context, event)
            if point is None:
                return {"RUNNING_MODAL"}

            if self.start is None:
                self.start = point
                self._set_header(context)
                return {"RUNNING_MODAL"}

            edge_id = self._add_line(context, self.start, point)
            if edge_id and self.auto_constraints:
                self._apply_auto_constraints(context, edge_id, self.start, point)
            if edge_id:
                obj = ensure_sketch_object(context)
                if obj is not None:
                    snapshot_state(obj, "Line")
            self.start = point
            self.input_str = ""
            self.preview_str = ""
            self._set_header(context)
            return {"RUNNING_MODAL"}

        return {"RUNNING_MODAL"}

    def _set_header(self, context):
        mode = "REL" if self.relative_mode else "ABS"
        auto = "AUTO" if self.auto_constraints else "MANUAL"
        snap = "SNAP" if self.snap_enabled else "FREE"
        axis = self.axis_lock if self.axis_lock else "-"
        ang = f"{self.angle_snap_deg:g}" if self.angle_snap_enabled else "-"
        text = self.input_str if self.input_str else "<input>"
        preview = f" | {self.preview_str}" if self.preview_str else ""
        context.area.header_text_set(
            f"Sketch Mode | {mode} | {auto} | {snap} | ANG:{ang} | LOCK:{axis} | {text}{preview}"
        )

    def _clear_header(self, context):
        context.area.header_text_set(None)

    def _parse_input(self, text):
        return parse_input(text, self.start, self.relative_mode)

    def _parse_polar(self, text):
        return parse_polar(text, self.start)

    def _mouse_to_plane(self, context, event):
        region = context.region
        rv3d = context.region_data
        coord = (event.mouse_region_x, event.mouse_region_y)

        origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
        direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)

        if abs(direction.z) < 1e-6:
            return None

        t = -origin.z / direction.z
        location = origin + direction * t
        location = Vector((location.x, location.y, 0.0))
        return self._snap_location(context, location, event)

    def _snap_location(self, context, location, event):
        if not self.snap_enabled or event.shift:
            return self._apply_angle_snap(self._apply_axis_lock(location))

        snapped = self._snap_to_features(context, location)
        if snapped is not None:
            return self._apply_angle_snap(self._apply_axis_lock(snapped))

        return self._apply_angle_snap(self._apply_axis_lock(self._snap_to_grid(context, location)))

    def _apply_axis_lock(self, location):
        return apply_axis_lock(location, self.start, self.axis_lock)

    def _apply_angle_snap(self, location):
        return apply_angle_snap(
            location,
            self.start,
            self.angle_snap_enabled,
            self.angle_snap_deg,
            self.axis_lock,
        )

    def _update_preview(self, context, event):
        if self.start is None:
            self.preview_str = ""
            return

        point = self._mouse_to_plane(context, event)
        if point is None:
            self.preview_str = ""
            return
        self.preview_str = format_preview(self.start, point)

    def _snap_to_grid(self, context, location):
        return snap_to_grid(
            location,
            self.grid_step,
            context.scene.unit_settings.scale_length,
            self.snap_grid,
        )

    def _grid_step(self, context):
        return grid_step_value(self.grid_step, context.scene.unit_settings.scale_length)

    def _snap_to_features(self, context, location):
        obj = context.scene.objects.get("AI_Sketch")
        return snap_to_features(
            location,
            obj,
            self.snap_radius,
            context.scene.unit_settings.scale_length,
            self.snap_verts,
            self.snap_mids,
            self.snap_inters,
        )

    def _collect_feature_points(self, context):
        obj = context.scene.objects.get("AI_Sketch")
        return collect_feature_points(obj, self.snap_verts, self.snap_mids, self.snap_inters)

    def _segment_intersections(self, segments):
        return segment_intersections(segments)

    def _segment_intersection(self, p1, p2, p3, p4):
        return segment_intersection(p1, p2, p3, p4)

    def _point_on_segment(self, px, py, x1, y1, x2, y2):
        return point_on_segment(px, py, x1, y1, x2, y2)

    def _add_line(self, context, start, end):
        obj = ensure_sketch_object(context)
        if obj is None:
            return None
        bm = bmesh.new()
        bm.from_mesh(obj.data)

        v1 = bm.verts.new((start.x, start.y, 0.0))
        v2 = bm.verts.new((end.x, end.y, 0.0))
        edge = bm.edges.new((v1, v2))
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.verts.index_update()
        bm.edges.index_update()
        edge_index = edge.index

        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()
        return str(edge_index)

    def _apply_auto_constraints(self, context, edge_id, start, end):
        obj = ensure_sketch_object(context)
        if obj is None:
            return
        dx = end.x - start.x
        dy = end.y - start.y
        if abs(dx) < 1e-8 and abs(dy) < 1e-8:
            return

        angle = abs(math.degrees(math.atan2(dy, dx)))
        constraints = []

        if angle < self.hv_tolerance_deg or abs(angle - 180.0) < self.hv_tolerance_deg:
            constraints.append(HorizontalConstraint(id=new_constraint_id(), line=edge_id))
        elif abs(angle - 90.0) < self.hv_tolerance_deg:
            constraints.append(VerticalConstraint(id=new_constraint_id(), line=edge_id))

        for constraint in constraints:
            append_constraint(obj, constraint)

        if constraints:
            solve_mesh(obj, load_constraints(obj))


class AIHELPER_OT_add_circle(bpy.types.Operator):
    bl_idname = "aihelper.add_circle"
    bl_label = "Add Circle"
    bl_description = "Add a circle to the sketch mesh"
    bl_options = {"REGISTER", "UNDO"}

    radius: bpy.props.FloatProperty(
        name="Radius",
        description="Circle radius",
        min=0.0,
        default=1.0,
    )
    segments: bpy.props.IntProperty(
        name="Segments",
        description="Circle resolution",
        min=3,
        max=256,
        default=32,
    )
    center_x: bpy.props.FloatProperty(
        name="Center X",
        description="Circle center X",
        default=0.0,
    )
    center_y: bpy.props.FloatProperty(
        name="Center Y",
        description="Circle center Y",
        default=0.0,
    )

    def invoke(self, context, _event):
        cursor = context.scene.cursor.location
        self.center_x = cursor.x
        self.center_y = cursor.y
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if self.radius <= 0.0:
            self.report({"WARNING"}, "Radius must be greater than 0")
            return {"CANCELLED"}

        obj = ensure_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        bm = bmesh.new()
        bm.from_mesh(obj.data)
        matrix = Matrix.Translation((self.center_x, self.center_y, 0.0))
        result = bmesh.ops.create_circle(
            bm,
            cap_ends=False,
            segments=self.segments,
            radius=self.radius,
            matrix=matrix,
        )
        center_vert = bm.verts.new((self.center_x, self.center_y, 0.0))
        bm.verts.ensure_lookup_table()
        bm.verts.index_update()
        circle_verts = result.get("verts", [])
        circle_ids = [str(v.index) for v in circle_verts]
        center_id = str(center_vert.index)

        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()

        circle_id = new_circle_id()
        append_circle(
            obj,
            {
                "id": circle_id,
                "center": center_id,
                "verts": circle_ids,
                "radius": float(self.radius),
            },
        )
        snapshot_state(obj, "Circle")

        self.report({"INFO"}, "Circle added")
        return {"FINISHED"}


class AIHELPER_OT_set_vertex_coords(bpy.types.Operator):
    bl_idname = "aihelper.set_vertex_coords"
    bl_label = "Set Vertex Coords"
    bl_description = "Set coordinates for the selected vertex"
    bl_options = {"REGISTER", "UNDO"}

    x: bpy.props.FloatProperty(
        name="X",
        description="X coordinate",
        default=0.0,
    )
    y: bpy.props.FloatProperty(
        name="Y",
        description="Y coordinate",
        default=0.0,
    )
    relative: bpy.props.BoolProperty(
        name="Relative",
        description="Apply coordinates as offsets",
        default=False,
    )

    def invoke(self, context, _event):
        obj = ensure_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        verts = _selected_vertices(obj)
        if len(verts) != 1:
            self.report({"WARNING"}, "Select 1 vertex")
            return {"CANCELLED"}

        v = verts[0]
        self.x = v.co.x
        self.y = v.co.y
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = ensure_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        verts = _selected_vertices(obj)
        if len(verts) != 1:
            self.report({"WARNING"}, "Select 1 vertex")
            return {"CANCELLED"}

        v = verts[0]
        if self.relative:
            v.co.x += self.x
            v.co.y += self.y
        else:
            v.co.x = self.x
            v.co.y = self.y
        v.co.z = 0.0
        obj.data.update()

        constraints = load_constraints(obj)
        if constraints:
            solve_mesh(obj, constraints)
        update_dimensions(context, obj, constraints)

        snapshot_state(obj, "Set Vertex Coords")
        self.report({"INFO"}, "Vertex updated")
        return {"FINISHED"}


class AIHELPER_OT_set_edge_length(bpy.types.Operator):
    bl_idname = "aihelper.set_edge_length"
    bl_label = "Set Edge Length"
    bl_description = "Set length for the selected edge"
    bl_options = {"REGISTER", "UNDO"}

    length: bpy.props.FloatProperty(
        name="Length",
        description="Target edge length",
        min=0.0,
        default=1.0,
    )
    anchor: bpy.props.EnumProperty(
        name="Anchor",
        description="Which part of the edge to keep fixed",
        items=[
            ("START", "Start", "Keep the first vertex fixed"),
            ("END", "End", "Keep the second vertex fixed"),
            ("CENTER", "Center", "Keep the midpoint fixed"),
        ],
        default="START",
    )

    def invoke(self, context, _event):
        obj = ensure_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        edges = _selected_edges(obj)
        if len(edges) != 1:
            self.report({"WARNING"}, "Select 1 edge")
            return {"CANCELLED"}

        edge = edges[0]
        v1 = obj.data.vertices[edge.vertices[0]]
        v2 = obj.data.vertices[edge.vertices[1]]
        self.length = (v2.co - v1.co).length
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = ensure_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        edges = _selected_edges(obj)
        if len(edges) != 1:
            self.report({"WARNING"}, "Select 1 edge")
            return {"CANCELLED"}

        edge = edges[0]
        v1 = obj.data.vertices[edge.vertices[0]]
        v2 = obj.data.vertices[edge.vertices[1]]
        vec = v2.co - v1.co
        length = vec.length
        if length < 1e-8:
            self.report({"WARNING"}, "Edge length too small")
            return {"CANCELLED"}

        direction = vec.normalized()
        target = max(self.length, 0.0)
        if self.anchor == "END":
            v1.co = v2.co - direction * target
        elif self.anchor == "CENTER":
            mid = (v1.co + v2.co) * 0.5
            offset = direction * (target * 0.5)
            v1.co = mid - offset
            v2.co = mid + offset
        else:
            v2.co = v1.co + direction * target

        v1.co.z = 0.0
        v2.co.z = 0.0
        obj.data.update()

        constraints = load_constraints(obj)
        if constraints:
            solve_mesh(obj, constraints)
        update_dimensions(context, obj, constraints)

        snapshot_state(obj, "Set Edge Length")
        self.report({"INFO"}, "Edge length updated")
        return {"FINISHED"}


class AIHELPER_OT_set_edge_angle(bpy.types.Operator):
    bl_idname = "aihelper.set_edge_angle"
    bl_label = "Set Edge Angle"
    bl_description = "Set angle for the selected edge"
    bl_options = {"REGISTER", "UNDO"}

    angle: bpy.props.FloatProperty(
        name="Angle",
        description="Target angle in degrees",
        default=0.0,
    )
    anchor: bpy.props.EnumProperty(
        name="Anchor",
        description="Which part of the edge to keep fixed",
        items=[
            ("START", "Start", "Keep the first vertex fixed"),
            ("END", "End", "Keep the second vertex fixed"),
            ("CENTER", "Center", "Keep the midpoint fixed"),
        ],
        default="START",
    )

    def invoke(self, context, _event):
        obj = ensure_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        edges = _selected_edges(obj)
        if len(edges) != 1:
            self.report({"WARNING"}, "Select 1 edge")
            return {"CANCELLED"}

        edge = edges[0]
        v1 = obj.data.vertices[edge.vertices[0]]
        v2 = obj.data.vertices[edge.vertices[1]]
        vec = v2.co - v1.co
        if vec.length > 1e-8:
            self.angle = math.degrees(math.atan2(vec.y, vec.x))
        else:
            self.angle = 0.0
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = ensure_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        edges = _selected_edges(obj)
        if len(edges) != 1:
            self.report({"WARNING"}, "Select 1 edge")
            return {"CANCELLED"}

        edge = edges[0]
        v1 = obj.data.vertices[edge.vertices[0]]
        v2 = obj.data.vertices[edge.vertices[1]]
        vec = v2.co - v1.co
        length = vec.length
        if length < 1e-8:
            self.report({"WARNING"}, "Edge length too small")
            return {"CANCELLED"}

        angle = math.radians(self.angle)
        direction = Vector((math.cos(angle), math.sin(angle), 0.0))
        if self.anchor == "END":
            v1.co = v2.co - direction * length
        elif self.anchor == "CENTER":
            mid = (v1.co + v2.co) * 0.5
            offset = direction * (length * 0.5)
            v1.co = mid - offset
            v2.co = mid + offset
        else:
            v2.co = v1.co + direction * length

        v1.co.z = 0.0
        v2.co.z = 0.0
        obj.data.update()

        constraints = load_constraints(obj)
        if constraints:
            solve_mesh(obj, constraints)
        update_dimensions(context, obj, constraints)

        snapshot_state(obj, "Set Edge Angle")
        self.report({"INFO"}, "Edge angle updated")
        return {"FINISHED"}


class AIHELPER_OT_set_angle_snap_preset(bpy.types.Operator):
    bl_idname = "aihelper.set_angle_snap_preset"
    bl_label = "Angle Snap Preset"
    bl_description = "Set the angle snap increment"
    bl_options = {"REGISTER", "UNDO"}

    angle: bpy.props.FloatProperty(
        name="Angle",
        description="Angle snap increment in degrees",
        default=15.0,
        min=1.0,
        max=90.0,
    )
    enable: bpy.props.BoolProperty(
        name="Enable",
        description="Enable angle snap",
        default=True,
        options={"HIDDEN"},
    )

    def execute(self, context):
        props = context.scene.ai_helper
        props.angle_snap_deg = self.angle
        if self.enable:
            props.angle_snap_enabled = True
        self.report({"INFO"}, f"Angle snap set to {self.angle:g} deg")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(AIHELPER_OT_sketch_mode)
    bpy.utils.register_class(AIHELPER_OT_add_circle)
    bpy.utils.register_class(AIHELPER_OT_set_vertex_coords)
    bpy.utils.register_class(AIHELPER_OT_set_edge_length)
    bpy.utils.register_class(AIHELPER_OT_set_edge_angle)
    bpy.utils.register_class(AIHELPER_OT_set_angle_snap_preset)


def unregister():
    bpy.utils.unregister_class(AIHELPER_OT_set_angle_snap_preset)
    bpy.utils.unregister_class(AIHELPER_OT_set_edge_angle)
    bpy.utils.unregister_class(AIHELPER_OT_set_edge_length)
    bpy.utils.unregister_class(AIHELPER_OT_set_vertex_coords)
    bpy.utils.unregister_class(AIHELPER_OT_add_circle)
    bpy.utils.unregister_class(AIHELPER_OT_sketch_mode)
