from __future__ import annotations

from typing import Any, Dict, List


def get_tool_schema() -> List[Dict[str, Any]]:
    return [
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
    ]
