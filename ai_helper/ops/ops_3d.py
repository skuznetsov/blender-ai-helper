import math

import bpy
import bmesh


def _get_sketch_object(context):
    obj = context.scene.objects.get("AI_Sketch")
    if obj is None or obj.type != "MESH":
        return None
    return obj


def _new_result_object(context, name_base: str, source):
    mesh = bpy.data.meshes.new(f"{name_base}_mesh")
    obj = bpy.data.objects.new(name_base, mesh)
    context.collection.objects.link(obj)
    obj["ai_helper_source"] = source.name
    return obj


def _replace_mesh(obj, new_mesh):
    old_mesh = obj.data
    obj.data = new_mesh
    if old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)


def _extrude_mesh_from_source(source, distance: float):
    mesh = bpy.data.meshes.new("AI_Extrude")
    bm = bmesh.new()
    bm.from_mesh(source.data)

    if not bm.edges:
        bm.free()
        return None

    res = bmesh.ops.extrude_edge_only(bm, edges=bm.edges)
    extruded = [elem for elem in res["geom"] if isinstance(elem, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=extruded, vec=(0.0, 0.0, distance))

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return mesh


class AIHELPER_OT_extrude_sketch(bpy.types.Operator):
    bl_idname = "aihelper.extrude_sketch"
    bl_label = "Extrude Sketch"
    bl_description = "Extrude the sketch edges along Z"
    bl_options = {"REGISTER", "UNDO"}

    distance: bpy.props.FloatProperty(
        name="Distance",
        description="Extrude distance",
        default=1.0,
    )

    def execute(self, context):
        source = _get_sketch_object(context)
        if source is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        mesh = _extrude_mesh_from_source(source, self.distance)
        if mesh is None:
            self.report({"WARNING"}, "Sketch has no edges")
            return {"CANCELLED"}

        obj = _new_result_object(context, "AI_Extrude", source)
        obj.data = mesh
        obj["ai_helper_op"] = "extrude"
        obj["ai_helper_extrude_distance"] = self.distance

        self.report({"INFO"}, "Extrude created")
        return {"FINISHED"}


class AIHELPER_OT_revolve_sketch(bpy.types.Operator):
    bl_idname = "aihelper.revolve_sketch"
    bl_label = "Revolve Sketch"
    bl_description = "Revolve the sketch edges around Z"
    bl_options = {"REGISTER", "UNDO"}

    angle: bpy.props.FloatProperty(
        name="Angle",
        description="Revolve angle (degrees)",
        default=360.0,
        min=0.0,
        max=360.0,
    )
    steps: bpy.props.IntProperty(
        name="Steps",
        description="Screw steps",
        default=32,
        min=3,
        max=512,
    )

    def execute(self, context):
        source = _get_sketch_object(context)
        if source is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        obj = _new_result_object(context, "AI_Revolve", source)
        obj.data = source.data.copy()
        obj["ai_helper_op"] = "revolve"
        obj["ai_helper_revolve_angle"] = self.angle
        obj["ai_helper_revolve_steps"] = self.steps

        mod = obj.modifiers.new(name="AI_Revolve", type="SCREW")
        mod.axis = "Z"
        mod.angle = math.radians(self.angle)
        mod.steps = self.steps
        mod.use_merge_vertices = True
        mod.merge_threshold = 0.001

        self.report({"INFO"}, "Revolve created")
        return {"FINISHED"}


class AIHELPER_OT_rebuild_3d_ops(bpy.types.Operator):
    bl_idname = "aihelper.rebuild_3d_ops"
    bl_label = "Rebuild 3D Ops"
    bl_description = "Rebuild 3D ops from their sketch source"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        rebuilt = rebuild_ops(context.scene)
        self.report({"INFO"}, f"Rebuilt {rebuilt} objects")
        return {"FINISHED"}


def has_ops(scene, source_name: str | None = None) -> bool:
    for obj in scene.objects:
        if obj.get("ai_helper_op") and obj.get("ai_helper_source"):
            if source_name is None or obj.get("ai_helper_source") == source_name:
                return True
    return False


def rebuild_ops(scene):
    rebuilt = 0
    for obj in scene.objects:
        op = obj.get("ai_helper_op")
        source_name = obj.get("ai_helper_source")
        if not op or not source_name:
            continue

        source = scene.objects.get(source_name)
        if source is None:
            continue

        if op == "extrude":
            distance = float(obj.get("ai_helper_extrude_distance", 1.0))
            mesh = _extrude_mesh_from_source(source, distance)
            if mesh is None:
                continue
            _replace_mesh(obj, mesh)
            rebuilt += 1
        elif op == "revolve":
            angle = float(obj.get("ai_helper_revolve_angle", 360.0))
            steps = int(obj.get("ai_helper_revolve_steps", 32))
            new_mesh = source.data.copy()
            _replace_mesh(obj, new_mesh)
            mod = obj.modifiers.get("AI_Revolve")
            if mod is None:
                mod = obj.modifiers.new(name="AI_Revolve", type="SCREW")
                mod.axis = "Z"
                mod.use_merge_vertices = True
                mod.merge_threshold = 0.001
            mod.angle = math.radians(angle)
            mod.steps = steps
            rebuilt += 1

    return rebuilt


def register():
    bpy.utils.register_class(AIHELPER_OT_extrude_sketch)
    bpy.utils.register_class(AIHELPER_OT_revolve_sketch)
    bpy.utils.register_class(AIHELPER_OT_rebuild_3d_ops)


def unregister():
    bpy.utils.unregister_class(AIHELPER_OT_rebuild_3d_ops)
    bpy.utils.unregister_class(AIHELPER_OT_revolve_sketch)
    bpy.utils.unregister_class(AIHELPER_OT_extrude_sketch)
