from __future__ import annotations

import json
import uuid
from typing import List

from .constraints import SketchConstraint, constraint_from_dict, constraints_to_dict


_CONSTRAINTS_KEY = "ai_helper_constraints"


def new_constraint_id() -> str:
    return uuid.uuid4().hex


def load_constraints(obj) -> List[SketchConstraint]:
    raw = obj.get(_CONSTRAINTS_KEY)
    if not raw:
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []

    constraints = []
    for item in data:
        try:
            constraints.append(constraint_from_dict(item))
        except ValueError:
            continue
    return constraints


def save_constraints(obj, constraints: List[SketchConstraint]) -> None:
    obj[_CONSTRAINTS_KEY] = json.dumps(constraints_to_dict(constraints))


def append_constraint(obj, constraint: SketchConstraint) -> None:
    constraints = load_constraints(obj)
    constraints.append(constraint)
    save_constraints(obj, constraints)


def clear_constraints(obj) -> None:
    if _CONSTRAINTS_KEY in obj:
        del obj[_CONSTRAINTS_KEY]
