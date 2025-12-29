import bpy

from ..core import reload as reload_utils


class AIHELPER_OT_reload_addon(bpy.types.Operator):
    bl_idname = "aihelper.reload_addon"
    bl_label = "Reload Add-on"
    bl_description = "Reload the AI Helper addon"
    bl_options = {"REGISTER"}

    def execute(self, _context):
        scheduled = reload_utils.schedule_reload()
        if scheduled:
            self.report({"INFO"}, "Reload scheduled")
        else:
            self.report({"INFO"}, "Reload already scheduled")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(AIHELPER_OT_reload_addon)


def unregister():
    bpy.utils.unregister_class(AIHELPER_OT_reload_addon)
