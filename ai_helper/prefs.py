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
    grok_model: bpy.props.StringProperty(
        name="Grok Model",
        description="Default model id for text-only requests",
        default="grok-4-1-fast-reasoning",
    )
    grok_vision_model: bpy.props.StringProperty(
        name="Grok Vision Model",
        description="Model id for vision requests (grok-4-1-fast-* supports data URLs)",
        default="grok-4-1-fast-reasoning",
    )
    grok_vision_image_url: bpy.props.StringProperty(
        name="Vision Image URL",
        description="Default HTTPS image URL used when no image path/url is set",
        default="",
    )
    grok_vision_upload_command: bpy.props.StringProperty(
        name="Vision Upload Command",
        description="Command that uploads a local image and prints a URL ({path} or {abs_path})",
        default="",
    )
    grok_vision_upload_timeout: bpy.props.IntProperty(
        name="Vision Upload Timeout",
        description="Timeout in seconds for the upload command",
        default=30,
        min=5,
        max=300,
    )

    def draw(self, _context):
        layout = self.layout
        layout.prop(self, "debug")
        layout.prop(self, "grok_adapter_path")
        layout.prop(self, "grok_model")
        layout.prop(self, "grok_vision_model")
        layout.prop(self, "grok_vision_image_url")
        layout.prop(self, "grok_vision_upload_command")
        layout.prop(self, "grok_vision_upload_timeout")
        layout.operator("aihelper.install_grok_deps", text="Install aiohttp")


def register():
    bpy.utils.register_class(AIHelperPreferences)


def unregister():
    bpy.utils.unregister_class(AIHelperPreferences)
