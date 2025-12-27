import time

import bpy
from bpy.app.handlers import persistent

from ..ops import ops_3d

_PENDING_REBUILD = False
_LAST_REBUILD = 0.0
_MIN_REBUILD_INTERVAL = 0.1


def _should_rebuild(scene, depsgraph) -> bool:
    for update in depsgraph.updates:
        obj = getattr(update, "id", None)
        if not isinstance(obj, bpy.types.Object):
            continue
        if obj.name != "AI_Sketch":
            continue
        if obj.is_updated_geometry or obj.is_updated_data:
            return ops_3d.has_ops(scene, obj.name)
    return False


def _schedule_rebuild(scene) -> None:
    global _PENDING_REBUILD
    if _PENDING_REBUILD:
        return
    _PENDING_REBUILD = True
    bpy.app.timers.register(lambda: _run_rebuild(scene), first_interval=_MIN_REBUILD_INTERVAL)


def _run_rebuild(scene):
    global _PENDING_REBUILD, _LAST_REBUILD
    _PENDING_REBUILD = False
    if not getattr(scene.ai_helper, "auto_rebuild", False):
        return None

    now = time.monotonic()
    if now - _LAST_REBUILD < _MIN_REBUILD_INTERVAL:
        return None

    ops_3d.rebuild_ops(scene)
    _LAST_REBUILD = time.monotonic()
    return None


@persistent
def ai_helper_depsgraph_handler(scene, depsgraph):
    if not getattr(scene.ai_helper, "auto_rebuild", False):
        return
    if _should_rebuild(scene, depsgraph):
        _schedule_rebuild(scene)


def register():
    if ai_helper_depsgraph_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(ai_helper_depsgraph_handler)


def unregister():
    if ai_helper_depsgraph_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(ai_helper_depsgraph_handler)
