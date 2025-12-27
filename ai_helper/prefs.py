import bpy

from .core import logger


def _update_debug(self, _context):
    logger.set_debug(self.debug)


class AIHelperPreferences(bpy.types.AddonPreferences):
    bl_idname = "ai_helper"

    debug: bpy.props.BoolProperty(
        name="Debug Logs",
        description="Enable verbose logging",
        default=False,
        update=_update_debug,
    )

    grok_adapter_path: bpy.props.StringProperty(
        name="Grok Adapter Path",
        description="Path to grok.py adapter",
        subtype="FILE_PATH",
        default="",
    )

    def draw(self, _context):
        layout = self.layout
        layout.prop(self, "debug")
        layout.prop(self, "grok_adapter_path")


def register():
    bpy.utils.register_class(AIHelperPreferences)


def unregister():
    bpy.utils.unregister_class(AIHelperPreferences)
