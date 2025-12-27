bl_info = {
    "name": "AI Helper",
    "author": "Sergey + Codex",
    "version": (0, 1, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > AI Helper",
    "description": "Sketch and LLM-assisted modeling tools",
    "category": "3D View",
}

try:
    import bpy  # noqa: F401
    _IN_BLENDER = True
except ModuleNotFoundError:
    _IN_BLENDER = False

if _IN_BLENDER:
    from . import prefs, props, ui
    from .core import handlers
    from .ops import constraints, llm, ops_3d, sketch
    _MODULES = (prefs, props, ui, llm, sketch, constraints, ops_3d, handlers)
else:
    _MODULES = ()


def register():
    if not _IN_BLENDER:
        raise RuntimeError("Blender bpy module not available")
    for module in _MODULES:
        module.register()


def unregister():
    if not _IN_BLENDER:
        return
    for module in reversed(_MODULES):
        module.unregister()
