import bpy
from mathutils import Vector

from .circles import load_circles
from .constraints import AngleConstraint, DistanceConstraint, RadiusConstraint


_DIMENSION_KEY = "ai_helper_dimension_id"
_DIMENSION_KIND_KEY = "ai_helper_dimension_kind"
_DIMENSION_PREFIX = "AI_DIM_"


def update_dimensions(context, sketch_obj, constraints):
    mesh = sketch_obj.data
    collection = sketch_obj.users_collection[0] if sketch_obj.users_collection else context.collection
    active_ids = {c.id for c in constraints if isinstance(c, (DistanceConstraint, AngleConstraint, RadiusConstraint))}
    circles = load_circles(sketch_obj)
    circle_map = {circle.get("id"): circle for circle in circles}

    for constraint in constraints:
        if isinstance(constraint, DistanceConstraint):
            try:
                v1 = mesh.vertices[int(constraint.p1)]
                v2 = mesh.vertices[int(constraint.p2)]
            except (ValueError, IndexError):
                continue

            text_obj = _ensure_label(constraint.id, constraint.kind, collection)
            text_obj.data.body = f"{constraint.distance:.3f}"
            text_obj.scale = (0.2, 0.2, 0.2)

            mid = (v1.co + v2.co) * 0.5
            world = sketch_obj.matrix_world @ mid
            text_obj.location = world
        elif isinstance(constraint, AngleConstraint):
            try:
                p1 = mesh.vertices[int(constraint.p1)]
                pv = mesh.vertices[int(constraint.vertex)]
                p2 = mesh.vertices[int(constraint.p2)]
            except (ValueError, IndexError):
                continue

            v1 = p1.co - pv.co
            v2 = p2.co - pv.co
            len1 = v1.length
            len2 = v2.length
            if len1 < 1e-6 or len2 < 1e-6:
                continue

            u1 = v1 / len1
            u2 = v2 / len2
            bis = u1 + u2
            if bis.length < 1e-6:
                bis = Vector((-u1.y, u1.x, 0.0))
            bis.normalize()
            offset = max(min(len1, len2) * 0.3, 0.2)

            text_obj = _ensure_label(constraint.id, constraint.kind, collection)
            text_obj.data.body = f"{constraint.degrees:.2f} deg"
            text_obj.scale = (0.2, 0.2, 0.2)

            pos = pv.co + bis * offset
            world = sketch_obj.matrix_world @ pos
            text_obj.location = world
        elif isinstance(constraint, RadiusConstraint):
            circle = circle_map.get(constraint.entity)
            if not circle:
                continue
            center_id = circle.get("center")
            if center_id is None:
                continue
            try:
                center = mesh.vertices[int(center_id)].co
            except (ValueError, IndexError):
                continue

            text_obj = _ensure_label(constraint.id, constraint.kind, collection)
            text_obj.data.body = f"R {constraint.radius:.3f}"
            text_obj.scale = (0.2, 0.2, 0.2)

            pos = center + Vector((constraint.radius, 0.0, 0.0))
            world = sketch_obj.matrix_world @ pos
            text_obj.location = world

    _remove_stale_dimensions(active_ids)


def clear_dimensions(context):
    to_remove = [obj for obj in bpy.data.objects if obj.get(_DIMENSION_KEY)]
    for obj in to_remove:
        bpy.data.objects.remove(obj, do_unlink=True)


def get_dimension_constraint_id(obj):
    return obj.get(_DIMENSION_KEY)


def get_dimension_kind(obj):
    return obj.get(_DIMENSION_KIND_KEY)


def _ensure_label(constraint_id, kind, collection):
    name = f"{_DIMENSION_PREFIX}{constraint_id[:6]}"
    text_obj = bpy.data.objects.get(name)
    if text_obj is None:
        curve = bpy.data.curves.new(name=name, type="FONT")
        text_obj = bpy.data.objects.new(name, curve)
        collection.objects.link(text_obj)
    text_obj[_DIMENSION_KEY] = constraint_id
    text_obj[_DIMENSION_KIND_KEY] = kind
    return text_obj


def _remove_stale_dimensions(active_ids):
    for obj in bpy.data.objects:
        cid = obj.get(_DIMENSION_KEY)
        if cid and cid not in active_ids:
            bpy.data.objects.remove(obj, do_unlink=True)
