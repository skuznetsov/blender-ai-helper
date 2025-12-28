import math

import bpy
import bmesh
from mathutils import Vector

from ..sketch.tags import resolve_tags

_SHELL_MOD = "AI_Shell"
_BEVEL_MOD = "AI_Bevel"


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


def _remove_modifier(obj, name: str) -> None:
    mod = obj.modifiers.get(name)
    if mod is not None:
        obj.modifiers.remove(mod)


def _ensure_shell_modifier(obj, thickness: float) -> None:
    mod = obj.modifiers.get(_SHELL_MOD)
    if mod is None:
        mod = obj.modifiers.new(name=_SHELL_MOD, type="SOLIDIFY")
    mod.thickness = thickness


def _ensure_bevel_modifier(obj, width: float, segments: int) -> None:
    mod = obj.modifiers.get(_BEVEL_MOD)
    if mod is None:
        mod = obj.modifiers.new(name=_BEVEL_MOD, type="BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "NONE"


def _apply_optional_modifiers(obj) -> None:
    thickness = obj.get("ai_helper_shell_thickness")
    if thickness is None or float(thickness) <= 0.0:
        _remove_modifier(obj, _SHELL_MOD)
    else:
        _ensure_shell_modifier(obj, float(thickness))

    width = obj.get("ai_helper_bevel_width")
    segments = obj.get("ai_helper_bevel_segments")
    if width is None or float(width) <= 0.0:
        _remove_modifier(obj, _BEVEL_MOD)
    else:
        segs = int(segments) if segments is not None else 2
        _ensure_bevel_modifier(obj, float(width), max(segs, 1))


def _get_active_op_object(context):
    obj = context.active_object
    if obj is None or obj.type != "MESH":
        return None
    if not obj.get("ai_helper_op"):
        return None
    return obj


def _extrude_mesh_from_source(source, distance: float, edge_indices=None):
    mesh = bpy.data.meshes.new("AI_Extrude")
    bm = bmesh.new()
    bm.from_mesh(source.data)

    bm.edges.ensure_lookup_table()
    edges = bm.edges
    if edge_indices:
        edges = [bm.edges[i] for i in edge_indices if 0 <= i < len(bm.edges)]

    if not edges:
        bm.free()
        return None

    res = bmesh.ops.extrude_edge_only(bm, edges=edges)
    extruded = [elem for elem in res["geom"] if isinstance(elem, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=extruded, vec=(0.0, 0.0, distance))

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return mesh


def _edge_components(source, edge_indices):
    edges = []
    for eid in edge_indices:
        if 0 <= eid < len(source.data.edges):
            edge = source.data.edges[eid]
            edges.append((eid, edge.vertices[0], edge.vertices[1]))
    if not edges:
        return []

    vert_to_edges = {}
    for eid, v1, v2 in edges:
        vert_to_edges.setdefault(v1, set()).add(eid)
        vert_to_edges.setdefault(v2, set()).add(eid)

    edge_lookup = {eid: (v1, v2) for eid, v1, v2 in edges}
    remaining = set(edge_lookup.keys())
    components = []
    while remaining:
        start = next(iter(remaining))
        stack = [start]
        component = set()
        while stack:
            current = stack.pop()
            if current not in remaining:
                continue
            remaining.remove(current)
            component.add(current)
            v1, v2 = edge_lookup[current]
            for v in (v1, v2):
                for neighbor in vert_to_edges.get(v, set()):
                    if neighbor in remaining:
                        stack.append(neighbor)
        components.append(sorted(component))
    return components


def _ordered_vertices_from_edges(source, edge_indices):
    adjacency = {}
    for eid in edge_indices:
        if eid < 0 or eid >= len(source.data.edges):
            continue
        edge = source.data.edges[eid]
        v1, v2 = edge.vertices
        adjacency.setdefault(v1, []).append(v2)
        adjacency.setdefault(v2, []).append(v1)

    if not adjacency:
        return None, None

    deg1 = [v for v, neighbors in adjacency.items() if len(neighbors) == 1]
    closed = False
    if deg1:
        start = min(deg1)
    else:
        if any(len(neighbors) != 2 for neighbors in adjacency.values()):
            return None, None
        closed = True
        start = min(adjacency.keys())

    order = [start]
    prev = None
    curr = start
    while True:
        neighbors = adjacency.get(curr, [])
        next_candidates = [n for n in neighbors if n != prev]
        if not next_candidates:
            break
        next_v = min(next_candidates)
        if closed and next_v == start:
            break
        if next_v in order:
            break
        order.append(next_v)
        prev, curr = curr, next_v
        if len(order) > len(adjacency):
            break

    if len(order) != len(adjacency):
        return None, None
    return order, closed


def _loft_mesh_from_source(source, edges_a, edges_b, offset_z):
    order_a, closed_a = _ordered_vertices_from_edges(source, edges_a)
    order_b, closed_b = _ordered_vertices_from_edges(source, edges_b)
    if not order_a or not order_b:
        return None
    if len(order_a) != len(order_b):
        return None
    if closed_a != closed_b:
        return None

    coords_a = [source.data.vertices[i].co.copy() for i in order_a]
    coords_b = [source.data.vertices[i].co.copy() for i in order_b]
    avg_z_a = sum(coord.z for coord in coords_a) / len(coords_a)
    avg_z_b = sum(coord.z for coord in coords_b) / len(coords_b)
    if abs(avg_z_a - avg_z_b) < 1e-6 and abs(offset_z) > 1e-6:
        coords_b = [Vector((c.x, c.y, c.z + offset_z)) for c in coords_b]

    mesh = bpy.data.meshes.new("AI_Loft")
    bm = bmesh.new()
    verts_a = [bm.verts.new(coord) for coord in coords_a]
    verts_b = [bm.verts.new(coord) for coord in coords_b]
    bm.verts.ensure_lookup_table()

    count = len(verts_a)
    if closed_a:
        pairs = [(i, (i + 1) % count) for i in range(count)]
    else:
        pairs = [(i, i + 1) for i in range(count - 1)]

    for i, j in pairs:
        try:
            bm.faces.new((verts_a[i], verts_a[j], verts_b[j], verts_b[i]))
        except ValueError:
            pass

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return mesh


def _path_vector_from_edges(source, edge_indices):
    order, closed = _ordered_vertices_from_edges(source, edge_indices)
    if not order or closed:
        return None
    start = source.data.vertices[order[0]].co
    end = source.data.vertices[order[-1]].co
    vec = end - start
    if vec.length < 1e-8:
        return None
    return vec


def _sweep_mesh_from_source(source, profile_edges, path_edges):
    vec = _path_vector_from_edges(source, path_edges)
    if vec is None:
        return None

    mesh = bpy.data.meshes.new("AI_Sweep")
    bm = bmesh.new()
    bm.from_mesh(source.data)
    bm.edges.ensure_lookup_table()

    edges = [bm.edges[i] for i in profile_edges if 0 <= i < len(bm.edges)]
    if not edges:
        bm.free()
        return None

    res = bmesh.ops.extrude_edge_only(bm, edges=edges)
    extruded = [elem for elem in res["geom"] if isinstance(elem, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=extruded, vec=vec)

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
    use_selection: bpy.props.BoolProperty(
        name="Use Selection",
        description="Extrude only selected edges when available",
        default=True,
    )

    def execute(self, context):
        source = _get_sketch_object(context)
        if source is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        edge_indices = None
        if self.use_selection:
            edge_indices = [e.index for e in source.data.edges if e.select]
            if not edge_indices:
                edge_indices = None

        mesh = _extrude_mesh_from_source(source, self.distance, edge_indices=edge_indices)
        if mesh is None:
            self.report({"WARNING"}, "Sketch has no edges")
            return {"CANCELLED"}

        obj = _new_result_object(context, "AI_Extrude", source)
        obj.data = mesh
        obj["ai_helper_op"] = "extrude"
        obj["ai_helper_extrude_distance"] = self.distance
        if edge_indices:
            obj["ai_helper_extrude_edges"] = list(edge_indices)
        _apply_optional_modifiers(obj)

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
        _apply_optional_modifiers(obj)

        self.report({"INFO"}, "Revolve created")
        return {"FINISHED"}


class AIHELPER_OT_loft_profiles(bpy.types.Operator):
    bl_idname = "aihelper.loft_profiles"
    bl_label = "Loft Profiles"
    bl_description = "Loft between two profile edge sets"
    bl_options = {"REGISTER", "UNDO"}

    profile_a_tag: bpy.props.StringProperty(
        name="Profile A Tag",
        description="Tag for the first profile edges",
        default="",
    )
    profile_b_tag: bpy.props.StringProperty(
        name="Profile B Tag",
        description="Tag for the second profile edges",
        default="",
    )
    offset_z: bpy.props.FloatProperty(
        name="Offset Z",
        description="Offset the second profile along Z when coplanar",
        default=1.0,
    )

    def execute(self, context):
        source = _get_sketch_object(context)
        if source is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        edges_a = []
        edges_b = []
        tag_a = self.profile_a_tag.strip()
        tag_b = self.profile_b_tag.strip()
        if tag_a and tag_b:
            _, edges_a = resolve_tags(source, [tag_a], prefer_center=False)
            _, edges_b = resolve_tags(source, [tag_b], prefer_center=False)
        else:
            selected = [e.index for e in source.data.edges if e.select]
            components = _edge_components(source, selected)
            if len(components) >= 2:
                edges_a, edges_b = components[0], components[1]

        edges_a = sorted(set(edges_a))
        edges_b = sorted(set(edges_b))
        if not edges_a or not edges_b:
            self.report({"WARNING"}, "Select two profiles or provide tags")
            return {"CANCELLED"}

        mesh = _loft_mesh_from_source(source, edges_a, edges_b, self.offset_z)
        if mesh is None:
            self.report({"WARNING"}, "Unable to loft profiles (check vertex counts)")
            return {"CANCELLED"}

        obj = _new_result_object(context, "AI_Loft", source)
        obj.data = mesh
        obj["ai_helper_op"] = "loft"
        obj["ai_helper_loft_edges_a"] = list(edges_a)
        obj["ai_helper_loft_edges_b"] = list(edges_b)
        obj["ai_helper_loft_offset_z"] = float(self.offset_z)
        _apply_optional_modifiers(obj)

        self.report({"INFO"}, "Loft created")
        return {"FINISHED"}


class AIHELPER_OT_sweep_profile(bpy.types.Operator):
    bl_idname = "aihelper.sweep_profile"
    bl_label = "Sweep Profile"
    bl_description = "Sweep profile edges along a path edge"
    bl_options = {"REGISTER", "UNDO"}

    profile_tag: bpy.props.StringProperty(
        name="Profile Tag",
        description="Tag for the profile edges",
        default="",
    )
    path_tag: bpy.props.StringProperty(
        name="Path Tag",
        description="Tag for the sweep path edges",
        default="",
    )

    def execute(self, context):
        source = _get_sketch_object(context)
        if source is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        profile_tag = self.profile_tag.strip()
        path_tag = self.path_tag.strip()
        if not profile_tag or not path_tag:
            self.report({"WARNING"}, "Profile and path tags are required")
            return {"CANCELLED"}

        _, profile_edges = resolve_tags(source, [profile_tag], prefer_center=False)
        _, path_edges = resolve_tags(source, [path_tag], prefer_center=False)
        profile_edges = sorted(set(profile_edges))
        path_edges = sorted(set(path_edges))
        if not profile_edges or not path_edges:
            self.report({"WARNING"}, "Profile/path tags have no edges")
            return {"CANCELLED"}

        mesh = _sweep_mesh_from_source(source, profile_edges, path_edges)
        if mesh is None:
            self.report({"WARNING"}, "Unable to sweep profile")
            return {"CANCELLED"}

        obj = _new_result_object(context, "AI_Sweep", source)
        obj.data = mesh
        obj["ai_helper_op"] = "sweep"
        obj["ai_helper_sweep_profile_edges"] = list(profile_edges)
        obj["ai_helper_sweep_path_edges"] = list(path_edges)
        _apply_optional_modifiers(obj)

        self.report({"INFO"}, "Sweep created")
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
            edge_indices = obj.get("ai_helper_extrude_edges")
            mesh = _extrude_mesh_from_source(source, distance, edge_indices=edge_indices)
            if mesh is None:
                continue
            _replace_mesh(obj, mesh)
            _apply_optional_modifiers(obj)
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
            _apply_optional_modifiers(obj)
            rebuilt += 1
        elif op == "loft":
            edges_a = obj.get("ai_helper_loft_edges_a") or []
            edges_b = obj.get("ai_helper_loft_edges_b") or []
            offset_z = float(obj.get("ai_helper_loft_offset_z", 0.0))
            mesh = _loft_mesh_from_source(source, edges_a, edges_b, offset_z)
            if mesh is None:
                continue
            _replace_mesh(obj, mesh)
            _apply_optional_modifiers(obj)
            rebuilt += 1
        elif op == "sweep":
            profile_edges = obj.get("ai_helper_sweep_profile_edges") or []
            path_edges = obj.get("ai_helper_sweep_path_edges") or []
            mesh = _sweep_mesh_from_source(source, profile_edges, path_edges)
            if mesh is None:
                continue
            _replace_mesh(obj, mesh)
            _apply_optional_modifiers(obj)
            rebuilt += 1

    return rebuilt


class AIHELPER_OT_add_shell_modifier(bpy.types.Operator):
    bl_idname = "aihelper.add_shell_modifier"
    bl_label = "Add Shell"
    bl_description = "Add a solidify shell to the selected 3D op"
    bl_options = {"REGISTER", "UNDO"}

    thickness: bpy.props.FloatProperty(
        name="Thickness",
        description="Shell thickness",
        min=0.0,
        default=0.1,
    )

    def invoke(self, context, _event):
        obj = _get_active_op_object(context)
        if obj is None:
            self.report({"WARNING"}, "Select a 3D op object")
            return {"CANCELLED"}

        existing = obj.get("ai_helper_shell_thickness")
        if existing is not None:
            self.thickness = float(existing)
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = _get_active_op_object(context)
        if obj is None:
            self.report({"WARNING"}, "Select a 3D op object")
            return {"CANCELLED"}

        thickness = max(self.thickness, 0.0)
        if thickness <= 0.0:
            self.report({"WARNING"}, "Thickness must be greater than 0")
            return {"CANCELLED"}

        obj["ai_helper_shell_thickness"] = thickness
        _apply_optional_modifiers(obj)
        self.report({"INFO"}, "Shell applied")
        return {"FINISHED"}


class AIHELPER_OT_clear_shell_modifier(bpy.types.Operator):
    bl_idname = "aihelper.clear_shell_modifier"
    bl_label = "Clear Shell"
    bl_description = "Remove shell modifier from selected 3D op"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = _get_active_op_object(context)
        if obj is None:
            self.report({"WARNING"}, "Select a 3D op object")
            return {"CANCELLED"}

        obj.pop("ai_helper_shell_thickness", None)
        _apply_optional_modifiers(obj)
        self.report({"INFO"}, "Shell removed")
        return {"FINISHED"}


class AIHELPER_OT_add_bevel_modifier(bpy.types.Operator):
    bl_idname = "aihelper.add_bevel_modifier"
    bl_label = "Add Fillet"
    bl_description = "Add a bevel fillet to the selected 3D op"
    bl_options = {"REGISTER", "UNDO"}

    width: bpy.props.FloatProperty(
        name="Width",
        description="Bevel width",
        min=0.0,
        default=0.05,
    )
    segments: bpy.props.IntProperty(
        name="Segments",
        description="Bevel segments",
        min=1,
        max=16,
        default=2,
    )

    def invoke(self, context, _event):
        obj = _get_active_op_object(context)
        if obj is None:
            self.report({"WARNING"}, "Select a 3D op object")
            return {"CANCELLED"}

        width = obj.get("ai_helper_bevel_width")
        if width is not None:
            self.width = float(width)
        segments = obj.get("ai_helper_bevel_segments")
        if segments is not None:
            self.segments = int(segments)
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = _get_active_op_object(context)
        if obj is None:
            self.report({"WARNING"}, "Select a 3D op object")
            return {"CANCELLED"}

        width = max(self.width, 0.0)
        if width <= 0.0:
            self.report({"WARNING"}, "Width must be greater than 0")
            return {"CANCELLED"}

        obj["ai_helper_bevel_width"] = width
        obj["ai_helper_bevel_segments"] = int(self.segments)
        _apply_optional_modifiers(obj)
        self.report({"INFO"}, "Fillet applied")
        return {"FINISHED"}


class AIHELPER_OT_clear_bevel_modifier(bpy.types.Operator):
    bl_idname = "aihelper.clear_bevel_modifier"
    bl_label = "Clear Fillet"
    bl_description = "Remove bevel from selected 3D op"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = _get_active_op_object(context)
        if obj is None:
            self.report({"WARNING"}, "Select a 3D op object")
            return {"CANCELLED"}

        obj.pop("ai_helper_bevel_width", None)
        obj.pop("ai_helper_bevel_segments", None)
        _apply_optional_modifiers(obj)
        self.report({"INFO"}, "Fillet removed")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(AIHELPER_OT_extrude_sketch)
    bpy.utils.register_class(AIHELPER_OT_revolve_sketch)
    bpy.utils.register_class(AIHELPER_OT_loft_profiles)
    bpy.utils.register_class(AIHELPER_OT_sweep_profile)
    bpy.utils.register_class(AIHELPER_OT_rebuild_3d_ops)
    bpy.utils.register_class(AIHELPER_OT_add_shell_modifier)
    bpy.utils.register_class(AIHELPER_OT_clear_shell_modifier)
    bpy.utils.register_class(AIHELPER_OT_add_bevel_modifier)
    bpy.utils.register_class(AIHELPER_OT_clear_bevel_modifier)


def unregister():
    bpy.utils.unregister_class(AIHELPER_OT_clear_bevel_modifier)
    bpy.utils.unregister_class(AIHELPER_OT_add_bevel_modifier)
    bpy.utils.unregister_class(AIHELPER_OT_clear_shell_modifier)
    bpy.utils.unregister_class(AIHELPER_OT_add_shell_modifier)
    bpy.utils.unregister_class(AIHELPER_OT_rebuild_3d_ops)
    bpy.utils.unregister_class(AIHELPER_OT_sweep_profile)
    bpy.utils.unregister_class(AIHELPER_OT_loft_profiles)
    bpy.utils.unregister_class(AIHELPER_OT_revolve_sketch)
    bpy.utils.unregister_class(AIHELPER_OT_extrude_sketch)
