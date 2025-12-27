import bpy


class AIHELPER_OT_sketch_mode(bpy.types.Operator):
    bl_idname = "aihelper.sketch_mode"
    bl_label = "Sketch Mode"
    bl_description = "Enter sketch mode (stub)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, _context):
        self.report({"INFO"}, "Sketch mode not implemented yet")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(AIHELPER_OT_sketch_mode)


def unregister():
    bpy.utils.unregister_class(AIHELPER_OT_sketch_mode)
