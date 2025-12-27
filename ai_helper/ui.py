import bpy


class AIHELPER_PT_main(bpy.types.Panel):
    bl_label = "AI Helper"
    bl_idname = "AIHELPER_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Helper"

    def draw(self, context):
        layout = self.layout
        props = context.scene.ai_helper

        layout.label(text="Prompt")
        layout.prop(props, "prompt", text="")
        row = layout.row(align=True)
        row.operator("aihelper.preview_prompt", text="Preview")
        row.operator("aihelper.apply_tool_calls", text="Apply")
        layout.prop(props, "tool_calls_json", text="Preview")
        layout.separator()
        layout.operator("aihelper.sketch_mode", text="Sketch Mode")


def register():
    bpy.utils.register_class(AIHELPER_PT_main)


def unregister():
    bpy.utils.unregister_class(AIHELPER_PT_main)
