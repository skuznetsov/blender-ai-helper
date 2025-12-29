from __future__ import annotations

from typing import Any, Dict, List


def get_tool_schema() -> List[Dict[str, Any]]:
    return [
        {
            "name": "clear_sketch",
            "description": "Clear all sketch geometry, constraints, circles, history, and tags",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "add_line",
            "description": "Add a line segment to the AI_Sketch on the XY plane",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_x": {"type": "number"},
                    "start_y": {"type": "number"},
                    "end_x": {"type": "number"},
                    "end_y": {"type": "number"},
                    "tag": {"type": "string"},
                    "auto_constraints": {"type": "boolean"},
                },
                "required": ["start_x", "start_y", "end_x", "end_y"],
            },
        },
        {
            "name": "add_circle",
            "description": "Add a circle to the AI_Sketch on the XY plane",
            "parameters": {
                "type": "object",
                "properties": {
                    "center_x": {"type": "number"},
                    "center_y": {"type": "number"},
                    "radius": {"type": "number"},
                    "segments": {"type": "integer"},
                    "tag": {"type": "string"},
                },
                "required": ["center_x", "center_y", "radius"],
            },
        },
        {
            "name": "add_arc",
            "description": "Add a circular arc to the AI_Sketch on the XY plane",
            "parameters": {
                "type": "object",
                "properties": {
                    "center_x": {"type": "number"},
                    "center_y": {"type": "number"},
                    "radius": {"type": "number"},
                    "start_angle": {"type": "number"},
                    "end_angle": {"type": "number"},
                    "segments": {"type": "integer"},
                    "clockwise": {"type": "boolean"},
                    "tag": {"type": "string"},
                },
                "required": ["center_x", "center_y", "radius", "start_angle", "end_angle"],
            },
        },
        {
            "name": "edit_arc",
            "description": "Edit a selected arc, optionally by tag",
            "parameters": {
                "type": "object",
                "properties": {
                    "center_x": {"type": "number"},
                    "center_y": {"type": "number"},
                    "radius": {"type": "number"},
                    "start_angle": {"type": "number"},
                    "end_angle": {"type": "number"},
                    "clockwise": {"type": "boolean"},
                    "tag": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        {
            "name": "add_polyline",
            "description": "Add a polyline to the AI_Sketch on the XY plane",
            "parameters": {
                "type": "object",
                "properties": {
                    "points": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {"type": "number"},
                            "minItems": 2,
                            "maxItems": 2,
                        },
                    },
                    "closed": {"type": "boolean"},
                    "tag": {"type": "string"},
                    "auto_constraints": {"type": "boolean"},
                },
                "required": ["points"],
            },
        },
        {
            "name": "add_rectangle",
            "description": "Add an axis-aligned rectangle to the AI_Sketch on the XY plane",
            "parameters": {
                "type": "object",
                "properties": {
                    "center_x": {"type": "number"},
                    "center_y": {"type": "number"},
                    "width": {"type": "number"},
                    "height": {"type": "number"},
                    "rotation_deg": {"type": "number"},
                    "tag": {"type": "string"},
                    "auto_constraints": {"type": "boolean"},
                },
                "required": ["center_x", "center_y", "width", "height"],
            },
        },
        {
            "name": "edit_rectangle",
            "description": "Edit a selected rectangle, optionally by tag",
            "parameters": {
                "type": "object",
                "properties": {
                    "center_x": {"type": "number"},
                    "center_y": {"type": "number"},
                    "width": {"type": "number"},
                    "height": {"type": "number"},
                    "rotation_deg": {"type": "number"},
                    "tag": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        {
            "name": "select_sketch_entities",
            "description": "Select sketch vertices/edges by index or tag",
            "parameters": {
                "type": "object",
                "properties": {
                    "verts": {"type": "array", "items": {"type": "integer"}},
                    "edges": {"type": "array", "items": {"type": "integer"}},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "extend": {"type": "boolean"},
                },
            },
        },
        {
            "name": "add_constraint",
            "description": "Add a sketch constraint using the current selection",
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": [
                            "distance",
                            "angle",
                            "radius",
                            "horizontal",
                            "vertical",
                            "coincident",
                            "midpoint",
                            "equal_length",
                            "concentric",
                            "symmetry",
                            "tangent",
                            "parallel",
                            "perpendicular",
                            "fix",
                        ],
                    },
                    "distance": {"type": "number"},
                    "degrees": {"type": "number"},
                    "radius": {"type": "number"},
                },
                "required": ["kind"],
            },
        },
        {
            "name": "solve_constraints",
            "description": "Solve sketch constraints",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "loft_profiles",
            "description": "Loft between tagged profile edge sets",
            "parameters": {
                "type": "object",
                "properties": {
                    "profile_tags": {"type": "array", "items": {"type": "string"}},
                    "profile_a_tag": {"type": "string"},
                    "profile_b_tag": {"type": "string"},
                    "offset_z": {"type": "number"},
                },
            },
        },
        {
            "name": "sweep_profile",
            "description": "Sweep a tagged profile along a tagged path",
            "parameters": {
                "type": "object",
                "properties": {
                    "profile_tag": {"type": "string"},
                    "path_tag": {"type": "string"},
                    "twist_deg": {"type": "number"},
                },
                "required": ["profile_tag", "path_tag"],
            },
        },
    ]
