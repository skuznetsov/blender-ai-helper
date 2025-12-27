from __future__ import annotations

from typing import Dict, Tuple

from ..solver import PointState, SolverDiagnostics, solve
from .circles import load_circles
from .constraints import DistanceConstraint, RadiusConstraint, SketchConstraint


def solve_mesh(obj, constraints: list[SketchConstraint]) -> SolverDiagnostics:
    mesh = obj.data
    points: Dict[str, PointState] = {}
    line_map: Dict[str, Tuple[str, str]] = {}

    for idx, vert in enumerate(mesh.vertices):
        points[str(idx)] = PointState(vert.co.x, vert.co.y)

    for edge in mesh.edges:
        line_map[str(edge.index)] = (str(edge.vertices[0]), str(edge.vertices[1]))

    expanded = _expand_radius_constraints(obj, constraints)
    diag = solve(points, expanded, line_map, max_iters=50, tolerance=1e-4)

    for idx, vert in enumerate(mesh.vertices):
        state = points.get(str(idx))
        if state:
            vert.co.x = state.x
            vert.co.y = state.y

    mesh.update()
    return diag


def _expand_radius_constraints(obj, constraints: list[SketchConstraint]) -> list[SketchConstraint]:
    circles = load_circles(obj)
    circle_map = {circle.get("id"): circle for circle in circles}
    expanded: list[SketchConstraint] = []

    for constraint in constraints:
        if isinstance(constraint, RadiusConstraint):
            circle = circle_map.get(constraint.entity)
            if not circle:
                continue
            center = circle.get("center")
            if center is None:
                continue
            for vid in circle.get("verts", []):
                expanded.append(
                    DistanceConstraint(
                        id=f"{constraint.id}:{vid}",
                        p1=str(center),
                        p2=str(vid),
                        distance=constraint.radius,
                    )
                )
        else:
            expanded.append(constraint)
    return expanded
