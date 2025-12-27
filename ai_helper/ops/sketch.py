import math

import bpy
import bmesh
from bpy_extras import view3d_utils
from mathutils import Vector


class AIHELPER_OT_sketch_mode(bpy.types.Operator):
    bl_idname = "aihelper.sketch_mode"
    bl_label = "Sketch Mode"
    bl_description = "Enter sketch mode"
    bl_options = {"REGISTER", "UNDO"}

    def __init__(self):
        self.start = None
        self.input_str = ""
        self.relative_mode = True

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
        return Vector((location.x, location.y, 0.0))

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
