import json
import subprocess
import sys

import bpy

from ..core import logger
from ..core.settings import get_prefs
from ..llm import GrokAdapter, dispatch_tool_calls, get_tool_schema, serialize_selection
from ..llm.presets import preset_fields, preset_params, preset_prompt, render_preset_prompt
from ..llm.recipes import recipe_prompt


class AIHELPER_OT_preview_prompt(bpy.types.Operator):
    bl_idname = "aihelper.preview_prompt"
    bl_label = "Preview Prompt"
    bl_description = "Generate tool call preview"
    bl_options = {"REGISTER"}

    def execute(self, context):
        props = context.scene.ai_helper
        prompt = props.prompt.strip()
        image_path = props.image_path.strip()
        image_url = props.image_url.strip()
        image_notes = props.image_notes.strip()
        prefs = get_prefs()
        default_image_url = ""
        if prefs and getattr(prefs, "grok_vision_image_url", None):
            default_image_url = prefs.grok_vision_image_url.strip()
        image_input = image_path or image_url or default_image_url
        if not prompt and not image_input:
            self.report({"WARNING"}, "Prompt and image are empty")
            return {"CANCELLED"}
        if not prompt:
            prompt = image_notes or "Generate a 2D sketch from the attached image."

        adapter_path = prefs.grok_adapter_path if prefs else ""
        use_mock = not adapter_path
        model = prefs.grok_model if prefs and prefs.grok_model.strip() else None
        vision_model = prefs.grok_vision_model if prefs and prefs.grok_vision_model.strip() else None
        upload_command = None
        upload_timeout = None
        if prefs and prefs.grok_vision_upload_command.strip():
            upload_command = prefs.grok_vision_upload_command.strip()
            upload_timeout = int(prefs.grok_vision_upload_timeout or 30)

        adapter = GrokAdapter(
            adapter_path=adapter_path,
            mock=use_mock,
            model=model,
            vision_model=vision_model,
        )
        selection = serialize_selection(context)
        tools = get_tool_schema()

        try:
            tool_calls = adapter.request_tool_calls(
                prompt,
                selection,
                tools=tools,
                use_mock=use_mock,
                image_path=image_input or None,
                image_notes=image_notes or None,
                upload_command=None if use_mock else upload_command,
                upload_timeout=upload_timeout,
            )
        except ModuleNotFoundError as exc:
            if "aiohttp" in str(exc):
                self.report(
                    {"ERROR"},
                    f"aiohttp missing. Install via Preferences or run: {sys.executable} -m pip install aiohttp",
                )
                return {"CANCELLED"}
            raise
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


class AIHELPER_OT_apply_prompt_preset(bpy.types.Operator):
    bl_idname = "aihelper.apply_prompt_preset"
    bl_label = "Apply Prompt Preset"
    bl_description = "Apply a preset prompt template"
    bl_options = {"REGISTER"}

    append: bpy.props.BoolProperty(
        name="Append",
        description="Append to the current prompt instead of replacing it",
        default=False,
    )

    def execute(self, context):
        props = context.scene.ai_helper
        preset_key = props.prompt_preset
        text = preset_prompt(preset_key)
        if not text:
            self.report({"WARNING"}, "Preset is empty")
            return {"CANCELLED"}

        if self.append and props.prompt.strip():
            props.prompt = f"{props.prompt.rstrip()}\n{text}"
        else:
            props.prompt = text

        self.report({"INFO"}, "Preset applied")
        return {"FINISHED"}


class AIHELPER_OT_apply_prompt_recipe(bpy.types.Operator):
    bl_idname = "aihelper.apply_prompt_recipe"
    bl_label = "Apply Prompt Recipe"
    bl_description = "Apply a prompt recipe template"
    bl_options = {"REGISTER"}

    append: bpy.props.BoolProperty(
        name="Append",
        description="Append to the current prompt instead of replacing it",
        default=False,
    )

    def execute(self, context):
        props = context.scene.ai_helper
        recipe_key = props.prompt_recipe
        text = recipe_prompt(recipe_key)
        if not text:
            self.report({"WARNING"}, "Recipe is empty")
            return {"CANCELLED"}

        if self.append and props.prompt.strip():
            props.prompt = f"{props.prompt.rstrip()}\n{text}"
        else:
            props.prompt = text

        self.report({"INFO"}, "Recipe applied")
        return {"FINISHED"}


class AIHELPER_OT_install_grok_deps(bpy.types.Operator):
    bl_idname = "aihelper.install_grok_deps"
    bl_label = "Install aiohttp"
    bl_description = "Install aiohttp into Blender's Python environment"
    bl_options = {"REGISTER"}

    def execute(self, _context):
        try:
            import ensurepip

            ensurepip.bootstrap()
        except Exception:
            pass

        cmd = [sys.executable, "-m", "pip", "install", "aiohttp"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except Exception as exc:
            self.report({"ERROR"}, f"Install failed: {exc}")
            return {"CANCELLED"}

        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            if detail:
                detail = detail.replace("\n", " ")[:200]
                self.report({"ERROR"}, f"Install failed: {detail}")
            else:
                self.report({"ERROR"}, "Install failed: pip error")
            return {"CANCELLED"}

        self.report({"INFO"}, "aiohttp installed")
        return {"FINISHED"}


class AIHELPER_OT_apply_param_preset(bpy.types.Operator):
    bl_idname = "aihelper.apply_param_preset"
    bl_label = "Apply Param Preset"
    bl_description = "Apply a parameterized prompt preset"
    bl_options = {"REGISTER"}

    preset_key: bpy.props.StringProperty(default="")
    append: bpy.props.BoolProperty(
        name="Append",
        description="Append to the current prompt instead of replacing it",
        default=False,
    )
    width: bpy.props.FloatProperty(name="Width", default=100.0, min=0.0)
    height: bpy.props.FloatProperty(name="Height", default=60.0, min=0.0)
    hole_radius: bpy.props.FloatProperty(name="Hole Radius", default=5.0, min=0.0)
    hole_offset_x: bpy.props.FloatProperty(name="Hole Offset X", default=30.0)
    hole_offset_y: bpy.props.FloatProperty(name="Hole Offset Y", default=15.0)
    leg_a: bpy.props.FloatProperty(name="Leg A", default=80.0, min=0.0)
    leg_b: bpy.props.FloatProperty(name="Leg B", default=80.0, min=0.0)
    thickness: bpy.props.FloatProperty(name="Thickness", default=20.0, min=0.0)
    slot_length: bpy.props.FloatProperty(name="Slot Length", default=60.0, min=0.0)
    slot_width: bpy.props.FloatProperty(name="Slot Width", default=12.0, min=0.0)
    slot_spacing: bpy.props.FloatProperty(name="Slot Spacing", default=40.0, min=0.0)
    frame_width: bpy.props.FloatProperty(name="Frame Width", default=120.0, min=0.0)
    frame_height: bpy.props.FloatProperty(name="Frame Height", default=80.0, min=0.0)
    frame_wall: bpy.props.FloatProperty(name="Frame Wall", default=10.0, min=0.0)
    bolt_count: bpy.props.FloatProperty(name="Bolt Count", default=6.0, min=1.0)
    bolt_circle_radius: bpy.props.FloatProperty(name="Bolt Circle Radius", default=40.0, min=0.0)
    bolt_hole_radius: bpy.props.FloatProperty(name="Bolt Hole Radius", default=3.0, min=0.0)

    def invoke(self, context, _event):
        self._sync_preset_key(context)
        defaults = preset_params(self.preset_key)
        for key, value in defaults.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, _context):
        layout = self.layout
        fields = preset_fields(self.preset_key)
        if not fields:
            layout.label(text="Preset has no parameters")
            return
        for key, label, _default in fields:
            if hasattr(self, key):
                layout.prop(self, key, text=label)

    def execute(self, context):
        self._sync_preset_key(context)
        fields = preset_fields(self.preset_key)
        values = {}
        for key, _label, _default in fields:
            if hasattr(self, key):
                values[key] = getattr(self, key)
        text = render_preset_prompt(self.preset_key, values)
        if not text:
            self.report({"WARNING"}, "Preset is empty")
            return {"CANCELLED"}

        props = context.scene.ai_helper
        if self.append and props.prompt.strip():
            props.prompt = f"{props.prompt.rstrip()}\n{text}"
        else:
            props.prompt = text
        self.report({"INFO"}, "Preset applied")
        return {"FINISHED"}

    def _sync_preset_key(self, context):
        if not self.preset_key:
            props = context.scene.ai_helper
            self.preset_key = props.prompt_preset


def register():
    bpy.utils.register_class(AIHELPER_OT_preview_prompt)
    bpy.utils.register_class(AIHELPER_OT_apply_tool_calls)
    bpy.utils.register_class(AIHELPER_OT_apply_prompt_preset)
    bpy.utils.register_class(AIHELPER_OT_apply_prompt_recipe)
    bpy.utils.register_class(AIHELPER_OT_install_grok_deps)
    bpy.utils.register_class(AIHELPER_OT_apply_param_preset)


def unregister():
    bpy.utils.unregister_class(AIHELPER_OT_apply_param_preset)
    bpy.utils.unregister_class(AIHELPER_OT_install_grok_deps)
    bpy.utils.unregister_class(AIHELPER_OT_apply_prompt_recipe)
    bpy.utils.unregister_class(AIHELPER_OT_apply_prompt_preset)
    bpy.utils.unregister_class(AIHELPER_OT_apply_tool_calls)
    bpy.utils.unregister_class(AIHELPER_OT_preview_prompt)
