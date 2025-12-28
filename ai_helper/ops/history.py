import bpy

from ..sketch.dimensions import update_dimensions
from ..sketch.history import load_history, restore_snapshot, snapshot_state


def _get_sketch_object(context):
    obj = context.scene.objects.get("AI_Sketch")
    if obj is None or obj.type != "MESH":
        return None
    return obj


class AIHELPER_OT_capture_snapshot(bpy.types.Operator):
    bl_idname = "aihelper.capture_snapshot"
    bl_label = "Capture Snapshot"
    bl_description = "Record the current sketch state"
    bl_options = {"REGISTER", "UNDO"}

    label: bpy.props.StringProperty(
        name="Label",
        description="Snapshot label",
        default="Snapshot",
    )

    def invoke(self, context, _event):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        history = load_history(obj)
        self.label = f"Snapshot {len(history) + 1}"
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        snapshot_state(obj, self.label)
        self.report({"INFO"}, "Snapshot captured")
        return {"FINISHED"}


class AIHELPER_OT_restore_snapshot(bpy.types.Operator):
    bl_idname = "aihelper.restore_snapshot"
    bl_label = "Restore Snapshot"
    bl_description = "Restore a sketch snapshot from history"
    bl_options = {"REGISTER", "UNDO"}

    index: bpy.props.IntProperty()

    def execute(self, context):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        history = load_history(obj)
        if not history:
            self.report({"WARNING"}, "No history available")
            return {"CANCELLED"}
        if self.index < 0 or self.index >= len(history):
            self.report({"WARNING"}, "Snapshot index out of range")
            return {"CANCELLED"}

        constraints = restore_snapshot(obj, history[self.index])
        update_dimensions(context, obj, constraints)
        self.report({"INFO"}, "Snapshot restored")
        return {"FINISHED"}


class AIHELPER_OT_clear_history(bpy.types.Operator):
    bl_idname = "aihelper.clear_history"
    bl_label = "Clear History"
    bl_description = "Clear sketch history snapshots"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = _get_sketch_object(context)
        if obj is None:
            self.report({"WARNING"}, "No sketch mesh found")
            return {"CANCELLED"}

        if "ai_helper_history" in obj:
            del obj["ai_helper_history"]
        self.report({"INFO"}, "History cleared")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(AIHELPER_OT_capture_snapshot)
    bpy.utils.register_class(AIHELPER_OT_restore_snapshot)
    bpy.utils.register_class(AIHELPER_OT_clear_history)


def unregister():
    bpy.utils.unregister_class(AIHELPER_OT_clear_history)
    bpy.utils.unregister_class(AIHELPER_OT_restore_snapshot)
    bpy.utils.unregister_class(AIHELPER_OT_capture_snapshot)
