import math

import bpy
import bmesh
from bpy_extras import view3d_utils
from mathutils import Vector

from ..sketch.quadtree import Point2D, Quadtree

class AIHELPER_OT_sketch_mode(bpy.types.Operator):
    bl_idname = "aihelper.sketch_mode"
    bl_label = "Sketch Mode"
    bl_description = "Enter sketch mode"
    bl_options = {"REGISTER", "UNDO"}

    def __init__(self):
        self.start = None
        self.input_str = ""
        self.relative_mode = True
        self.snap_enabled = True
        self.snap_grid = True
        self.snap_verts = True
        self.snap_mids = True
        self.snap_inters = True
        self.snap_radius = 0.25
        self.grid_step = 1.0

    def invoke(self, context, event):
        if context.area.type != "VIEW_3D":
            self.report({"WARNING"}, "Sketch Mode requires a 3D View")
            return {"CANCELLED"}

        self.start = None
        self.input_str = ""
        self.relative_mode = True
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

        if event.type == "BACK_SPACE" and event.value == "PRESS":
            self.input_str = self.input_str[:-1]
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

            self._add_line(context, self.start, end)
            self.start = end
            self.input_str = ""
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

            self._add_line(context, self.start, point)
            self.start = point
            self.input_str = ""
            self._set_header(context)
            return {"RUNNING_MODAL"}

        return {"RUNNING_MODAL"}

    def _set_header(self, context):
        mode = "REL" if self.relative_mode else "ABS"
        text = self.input_str if self.input_str else "<input>"
        context.area.header_text_set(f"Sketch Mode | {mode} | {text}")

    def _clear_header(self, context):
        context.area.header_text_set(None)

    def _parse_input(self, text):
        text = text.strip()
        if not text:
            return None

        if text.startswith("@"):
            return self._parse_polar(text)

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

        if absolute or not self.relative_mode:
            return Vector((x, y, 0.0))
        if self.start is None:
            return None
        return Vector((self.start.x + x, self.start.y + y, 0.0))

    def _parse_polar(self, text):
        if self.start is None:
            return None

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
        return Vector((self.start.x + dx, self.start.y + dy, 0.0))

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
            return location

        snapped = self._snap_to_features(context, location)
        if snapped is not None:
            return snapped

        return self._snap_to_grid(context, location)

    def _snap_to_grid(self, context, location):
        if not self.snap_grid:
            return location

        step = self._grid_step(context)
        if step <= 0.0:
            return location

        x = math.floor(location.x / step + 0.5) * step
        y = math.floor(location.y / step + 0.5) * step
        return Vector((x, y, 0.0))

    def _grid_step(self, context):
        scale = context.scene.unit_settings.scale_length or 1.0
        return self.grid_step * scale

    def _snap_to_features(self, context, location):
        points = self._collect_feature_points(context)
        if not points:
            return None

        tree = Quadtree.build(points)
        nearest = tree.query_nearest(Point2D(location.x, location.y), k=1)
        if not nearest:
            return None

        radius = self.snap_radius * (context.scene.unit_settings.scale_length or 1.0)
        candidate = nearest[0]
        if candidate.distance_to(Point2D(location.x, location.y)) <= radius:
            return Vector((candidate.x, candidate.y, 0.0))

        return None

    def _collect_feature_points(self, context):
        obj = context.scene.objects.get("AI_Sketch")
        if obj is None or obj.type != "MESH":
            return []

        verts = obj.data.vertices
        points = []
        segments = []

        for v in verts:
            pos = obj.matrix_world @ v.co
            if self.snap_verts:
                points.append(Point2D(pos.x, pos.y, payload=("vert", v.index)))

        for edge in obj.data.edges:
            v1 = verts[edge.vertices[0]]
            v2 = verts[edge.vertices[1]]
            p1 = obj.matrix_world @ v1.co
            p2 = obj.matrix_world @ v2.co
            segments.append((p1, p2, v1.index, v2.index))

            if self.snap_mids:
                mid = (p1 + p2) * 0.5
                points.append(Point2D(mid.x, mid.y, payload=("mid", edge.index)))

        if self.snap_inters and len(segments) > 1:
            points.extend(self._segment_intersections(segments))

        return points

    def _segment_intersections(self, segments):
        hits = []
        count = len(segments)
        for i in range(count):
            a1, a2, a_idx1, a_idx2 = segments[i]
            for j in range(i + 1, count):
                b1, b2, b_idx1, b_idx2 = segments[j]
                if a_idx1 in (b_idx1, b_idx2) or a_idx2 in (b_idx1, b_idx2):
                    continue
                hit = self._segment_intersection(a1, a2, b1, b2)
                if hit is not None:
                    hits.append(Point2D(hit.x, hit.y, payload=("inter", i, j)))
        return hits

    def _segment_intersection(self, p1, p2, p3, p4):
        x1, y1 = p1.x, p1.y
        x2, y2 = p2.x, p2.y
        x3, y3 = p3.x, p3.y
        x4, y4 = p4.x, p4.y

        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < 1e-8:
            return None

        px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / denom
        py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / denom

        if not self._point_on_segment(px, py, x1, y1, x2, y2):
            return None
        if not self._point_on_segment(px, py, x3, y3, x4, y4):
            return None

        return Vector((px, py, 0.0))

    def _point_on_segment(self, px, py, x1, y1, x2, y2):
        min_x = min(x1, x2) - 1e-6
        max_x = max(x1, x2) + 1e-6
        min_y = min(y1, y2) - 1e-6
        max_y = max(y1, y2) + 1e-6
        return min_x <= px <= max_x and min_y <= py <= max_y

    def _ensure_sketch_object(self, context):
        name = "AI_Sketch"
        obj = context.scene.objects.get(name)
        if obj:
            return obj

        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        context.collection.objects.link(obj)
        return obj

    def _add_line(self, context, start, end):
        obj = self._ensure_sketch_object(context)
        bm = bmesh.new()
        bm.from_mesh(obj.data)

        v1 = bm.verts.new((start.x, start.y, 0.0))
        v2 = bm.verts.new((end.x, end.y, 0.0))
        bm.edges.new((v1, v2))

        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()


def register():
    bpy.utils.register_class(AIHELPER_OT_sketch_mode)


def unregister():
    bpy.utils.unregister_class(AIHELPER_OT_sketch_mode)
