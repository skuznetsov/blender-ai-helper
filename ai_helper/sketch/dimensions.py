import bpy

from .constraints import DistanceConstraint


_DIMENSION_KEY = "ai_helper_dimension_id"
_DIMENSION_PREFIX = "AI_DIM_"


def update_distance_dimensions(context, sketch_obj, constraints):
    mesh = sketch_obj.data
    collection = sketch_obj.users_collection[0] if sketch_obj.users_collection else context.collection
    active_ids = {c.id for c in constraints if isinstance(c, DistanceConstraint)}

    for constraint in constraints:
        if not isinstance(constraint, DistanceConstraint):
            continue

        try:
            v1 = mesh.vertices[int(constraint.p1)]
            v2 = mesh.vertices[int(constraint.p2)]
        except (ValueError, IndexError):
            continue

        name = f"{_DIMENSION_PREFIX}{constraint.id[:6]}"
        text_obj = bpy.data.objects.get(name)
        if text_obj is None:
            curve = bpy.data.curves.new(name=name, type="FONT")
            text_obj = bpy.data.objects.new(name, curve)
            text_obj[_DIMENSION_KEY] = constraint.id
            collection.objects.link(text_obj)

        text_obj.data.body = f"{constraint.distance:.3f}"
        text_obj.scale = (0.2, 0.2, 0.2)

        mid = (v1.co + v2.co) * 0.5
        world = sketch_obj.matrix_world @ mid
        text_obj.location = world

    _remove_stale_dimensions(active_ids)


def clear_dimensions(context):
    to_remove = [obj for obj in bpy.data.objects if obj.get(_DIMENSION_KEY)]
    for obj in to_remove:
        bpy.data.objects.remove(obj, do_unlink=True)


def get_dimension_constraint_id(obj):
    return obj.get(_DIMENSION_KEY)


def _remove_stale_dimensions(active_ids):
    for obj in bpy.data.objects:
        cid = obj.get(_DIMENSION_KEY)
        if cid and cid not in active_ids:
            bpy.data.objects.remove(obj, do_unlink=True)
