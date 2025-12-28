from __future__ import annotations

from typing import Dict, List, Tuple

RECIPES: Dict[str, Dict[str, str]] = {
    "NONE": {
        "label": "Select recipe",
        "description": "",
        "prompt": "",
    },
    "SKETCH_FROM_NOTES": {
        "label": "Sketch from notes",
        "description": "Turn notes into a clean 2D sketch with tags and constraints.",
        "prompt": (
            "Create a clean 2D sketch from the description. Use add_line/add_circle/add_arc/add_polyline/"
            "add_rectangle on the XY plane. Tag main geometry (profile, holes, slots). Add distance/angle/"
            "radius constraints and call solve_constraints."
        ),
    },
    "AUTO_CONSTRAIN": {
        "label": "Auto-constrain selection",
        "description": "Add constraints to the selected sketch entities.",
        "prompt": (
            "Analyze the selected sketch entities. Add horizontal/vertical constraints for axis-aligned edges, "
            "equal_length for repeated lengths, concentric for shared centers, and symmetry where obvious. "
            "Add distance/angle/radius constraints for key dimensions. Call solve_constraints at the end."
        ),
    },
    "PLATE_BOLT_CIRCLE": {
        "label": "Plate + bolt circle",
        "description": "Create a plate and a simple bolt circle pattern.",
        "prompt": (
            "Create a rectangular plate 120x80 centered at (0,0). Add a bolt circle of 6 holes with radius 3 "
            "on a circle radius 35. Tag the plate as plate and holes as bolt1..bolt6. Add radius constraints for "
            "holes and distance constraints for plate size."
        ),
    },
    "FRAME_FROM_BOUNDS": {
        "label": "Frame from bounds",
        "description": "Build a rectangular frame around the current sketch bounds.",
        "prompt": (
            "Use the sketch bounds from the selection summary. Create an outer rectangle 10% larger than the "
            "bounds and an inner rectangle 10% smaller. Center them at the bounds center. Tag outer as frame_outer "
            "and inner as frame_inner. Add distance constraints for both rectangles."
        ),
    },
    "SLOT_PAIR": {
        "label": "Slot pair",
        "description": "Create two aligned slots on the XY plane.",
        "prompt": (
            "Create two slots centered at (-30,0) and (30,0) with length 60 and width 12. For each slot, add two "
            "circles of radius 6 at offsets (-24,0) and (24,0) relative to the slot center, then connect with lines "
            "to form the outline. Tag slots as slot1/slot2 and circles as slot1_end1/slot1_end2 and slot2_end1/"
            "slot2_end2. Add radius constraints for the circles."
        ),
    },
}


def recipe_items() -> List[Tuple[str, str, str]]:
    items = []
    for key, value in RECIPES.items():
        items.append((key, str(value.get("label", key)), str(value.get("description", ""))))
    return items


def recipe_prompt(key: str) -> str:
    return str(RECIPES.get(key, {}).get("prompt", ""))


def recipe_description(key: str) -> str:
    return str(RECIPES.get(key, {}).get("description", ""))
