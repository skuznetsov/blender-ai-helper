import json

import bpy

from ..core import logger
from ..core.settings import get_prefs
from ..llm import GrokAdapter, dispatch_tool_calls, serialize_selection


class AIHELPER_OT_preview_prompt(bpy.types.Operator):
    bl_idname = "aihelper.preview_prompt"
    bl_label = "Preview Prompt"
    bl_description = "Generate tool call preview"
    bl_options = {"REGISTER"}

    def execute(self, context):
        props = context.scene.ai_helper
        prompt = props.prompt.strip()
        if not prompt:
            self.report({"WARNING"}, "Prompt is empty")
            return {"CANCELLED"}

        prefs = get_prefs()
        adapter_path = prefs.grok_adapter_path if prefs else ""
        use_mock = not adapter_path

        adapter = GrokAdapter(adapter_path=adapter_path, mock=use_mock)
        selection = serialize_selection(context)

        try:
            tool_calls = adapter.request_tool_calls(prompt, selection, use_mock=use_mock)
        except Exception as exc:
            logger.logger.error("Grok preview failed: %s", exc)
            self.report({"ERROR"}, f"Preview failed: {exc}")
            return {"CANCELLED"}

        payload = {"tool_calls": [call.to_dict() for call in tool_calls]}
        props.tool_calls_json = json.dumps(payload, indent=2)

        self.report({"INFO"}, "Preview ready")
        return {"FINISHED"}


class AIHELPER_OT_apply_tool_calls(bpy.types.Operator):
    bl_idname = "aihelper.apply_tool_calls"
    bl_label = "Apply Tool Calls"
    bl_description = "Apply tool calls to the scene"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.ai_helper
        raw = props.tool_calls_json.strip()
        if not raw:
            self.report({"WARNING"}, "No preview available")
            return {"CANCELLED"}

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            self.report({"ERROR"}, f"Invalid JSON: {exc}")
            return {"CANCELLED"}

        tool_calls = data.get("tool_calls", [])
        if not tool_calls:
            self.report({"WARNING"}, "No tool calls to apply")
            return {"CANCELLED"}

        result = dispatch_tool_calls(tool_calls, context, preview=False)
        if result["errors"]:
            logger.logger.warning("Tool call errors: %s", result["errors"])
            self.report({"WARNING"}, f"Errors: {len(result['errors'])}")
        else:
            self.report({"INFO"}, "Tool calls applied")

        return {"FINISHED"}


def register():
    bpy.utils.register_class(AIHELPER_OT_preview_prompt)
    bpy.utils.register_class(AIHELPER_OT_apply_tool_calls)


def unregister():
    bpy.utils.unregister_class(AIHELPER_OT_apply_tool_calls)
    bpy.utils.unregister_class(AIHELPER_OT_preview_prompt)
