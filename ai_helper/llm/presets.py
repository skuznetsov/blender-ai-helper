from __future__ import annotations

from typing import Dict, List, Tuple

PRESETS: Dict[str, Dict[str, object]] = {
    "NONE": {
        "label": "Select preset",
        "prompt": "",
        "params": [],
    },
    "PLATE_4_HOLES": {
        "label": "Plate with 4 holes",
        "params": [
            ("width", "Plate Width", 100.0),
            ("height", "Plate Height", 60.0),
            ("hole_radius", "Hole Radius", 5.0),
            ("hole_offset_x", "Hole Offset X", 30.0),
            ("hole_offset_y", "Hole Offset Y", 15.0),
        ],
        "builder": "_build_plate_prompt",
    },
    "L_BRACKET": {
        "label": "L bracket",
        "params": [
            ("leg_a", "Leg A", 80.0),
            ("leg_b", "Leg B", 80.0),
            ("thickness", "Thickness", 20.0),
        ],
        "builder": "_build_bracket_prompt",
    },
    "SLOT": {
        "label": "Slot",
        "params": [
            ("slot_length", "Slot Length", 60.0),
            ("slot_width", "Slot Width", 12.0),
        ],
        "builder": "_build_slot_prompt",
    },
    "FRAME": {
        "label": "Rectangular frame",
        "params": [
            ("frame_width", "Frame Width", 120.0),
            ("frame_height", "Frame Height", 80.0),
            ("frame_wall", "Frame Wall", 10.0),
        ],
        "builder": "_build_frame_prompt",
    },
    "BOLT_CIRCLE": {
        "label": "Bolt circle",
        "params": [
            ("bolt_count", "Bolt Count", 6.0),
            ("bolt_circle_radius", "Bolt Circle Radius", 40.0),
            ("bolt_hole_radius", "Bolt Hole Radius", 3.0),
        ],
        "builder": "_build_bolt_circle_prompt",
    },
    "SLOT_PAIR": {
        "label": "Slot pair",
        "params": [
            ("slot_length", "Slot Length", 60.0),
            ("slot_width", "Slot Width", 12.0),
            ("slot_spacing", "Slot Spacing", 40.0),
        ],
        "builder": "_build_slot_pair_prompt",
    },
}


def preset_items() -> List[Tuple[str, str, str]]:
    items = []
    for key, value in PRESETS.items():
        items.append((key, str(value.get("label", key)), ""))
    return items


def preset_fields(key: str) -> List[Tuple[str, str, float]]:
    preset = PRESETS.get(key, {})
    fields = preset.get("params", [])
    return [(str(name), str(label), float(default)) for name, label, default in fields]


def preset_params(key: str) -> Dict[str, float]:
    params: Dict[str, float] = {}
    for name, _label, default in preset_fields(key):
        params[name] = float(default)
    return params


def preset_prompt(key: str) -> str:
    return render_preset_prompt(key, {})


def render_preset_prompt(key: str, values: Dict[str, float]) -> str:
    preset = PRESETS.get(key)
    if not preset:
        return ""

    params = preset_params(key)
    for name, value in values.items():
        if value is None:
            continue
        params[name] = float(value)

    builder_name = preset.get("builder")
    if builder_name == "_build_plate_prompt":
        return _build_plate_prompt(params)
    if builder_name == "_build_bracket_prompt":
        return _build_bracket_prompt(params)
    if builder_name == "_build_slot_prompt":
        return _build_slot_prompt(params)
    if builder_name == "_build_frame_prompt":
        return _build_frame_prompt(params)
    if builder_name == "_build_bolt_circle_prompt":
        return _build_bolt_circle_prompt(params)
    if builder_name == "_build_slot_pair_prompt":
        return _build_slot_pair_prompt(params)

    return str(preset.get("prompt", ""))


def _build_plate_prompt(params: Dict[str, float]) -> str:
    width = params.get("width", 100.0)
    height = params.get("height", 60.0)
    hole_radius = params.get("hole_radius", 5.0)
    offset_x = params.get("hole_offset_x", 30.0)
    offset_y = params.get("hole_offset_y", 15.0)
    return (
        f"Create a 2D sketch of a rectangular plate {width:g}x{height:g} centered at (0,0). "
        f"Add 4 holes of radius {hole_radius:g} at "
        f"({offset_x:g},{offset_y:g}), (-{offset_x:g},{offset_y:g}), "
        f"(-{offset_x:g},-{offset_y:g}), ({offset_x:g},-{offset_y:g}). "
        "Use add_rectangle and add_circle. Tag the outer rectangle as plate and holes as hole1..hole4. "
        "Add radius constraints for each hole and distance constraints for plate size."
    )


def _build_bracket_prompt(params: Dict[str, float]) -> str:
    leg_a = params.get("leg_a", 80.0)
    leg_b = params.get("leg_b", 80.0)
    thickness = params.get("thickness", 20.0)
    return (
        "Create an L-shaped bracket as a closed polyline with points: "
        f"(0,0) -> ({leg_a:g},0) -> ({leg_a:g},{thickness:g}) -> "
        f"({thickness:g},{thickness:g}) -> ({thickness:g},{leg_b:g}) -> (0,{leg_b:g}) -> (0,0). "
        "Tag the polyline as bracket and add horizontal/vertical constraints."
    )


def _build_slot_prompt(params: Dict[str, float]) -> str:
    length = params.get("slot_length", 60.0)
    width = params.get("slot_width", 12.0)
    radius = width * 0.5
    offset = max((length - width) * 0.5, 0.0)
    return (
        f"Create a slot centered at (0,0) with length {length:g} and width {width:g}. "
        f"Add two circles of radius {radius:g} at (-{offset:g},0) and ({offset:g},0), "
        "then connect with lines to form a slot outline. Tag the slot as slot and the circles as end1/end2. "
        "Add radius constraints for the circles."
    )


def _build_frame_prompt(params: Dict[str, float]) -> str:
    width = params.get("frame_width", 120.0)
    height = params.get("frame_height", 80.0)
    wall = max(params.get("frame_wall", 10.0), 0.0)
    inner_width = max(width - wall * 2.0, 0.0)
    inner_height = max(height - wall * 2.0, 0.0)
    return (
        f"Create a 2D sketch of a rectangular frame. Add an outer rectangle {width:g}x{height:g} centered at (0,0). "
        f"Add an inner rectangle {inner_width:g}x{inner_height:g} centered at (0,0) for the cutout. "
        "Tag the outer rectangle as frame_outer and the inner rectangle as frame_inner. "
        "Add distance constraints for outer and inner sizes."
    )


def _build_bolt_circle_prompt(params: Dict[str, float]) -> str:
    count = max(int(round(params.get("bolt_count", 6.0))), 1)
    circle_radius = params.get("bolt_circle_radius", 40.0)
    hole_radius = params.get("bolt_hole_radius", 3.0)
    return (
        f"Create a bolt circle centered at (0,0) with radius {circle_radius:g}. "
        f"Add {count} holes of radius {hole_radius:g} evenly spaced on the circle (360/{count} degrees). "
        "Use add_circle for each hole, tag them bolt1..boltN. "
        "Add radius constraints for each hole and distance constraints from origin to each hole center."
    )


def _build_slot_pair_prompt(params: Dict[str, float]) -> str:
    length = params.get("slot_length", 60.0)
    width = params.get("slot_width", 12.0)
    spacing = params.get("slot_spacing", 40.0)
    radius = width * 0.5
    offset = max((length - width) * 0.5, 0.0)
    half_spacing = spacing * 0.5
    return (
        f"Create two slots centered at (-{half_spacing:g},0) and ({half_spacing:g},0) with length {length:g} and width "
        f"{width:g}. For each slot, add two circles of radius {radius:g} at offsets (-{offset:g},0) and "
        f"({offset:g},0) relative to the slot center, then connect with lines to form the slot outline. "
        "Tag slots as slot1/slot2 and the circles as slot1_end1/slot1_end2 and slot2_end1/slot2_end2. "
        "Add radius constraints for the circles."
    )
