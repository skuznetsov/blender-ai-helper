from __future__ import annotations

from typing import Dict, Tuple

from ..solver import PointState, SolverDiagnostics, solve
from .constraints import SketchConstraint


def solve_mesh(obj, constraints: list[SketchConstraint]) -> SolverDiagnostics:
    mesh = obj.data
    points: Dict[str, PointState] = {}
    line_map: Dict[str, Tuple[str, str]] = {}

    for idx, vert in enumerate(mesh.vertices):
        points[str(idx)] = PointState(vert.co.x, vert.co.y)

    for edge in mesh.edges:
        line_map[str(edge.index)] = (str(edge.vertices[0]), str(edge.vertices[1]))

    diag = solve(points, constraints, line_map, max_iters=50, tolerance=1e-4)

    for idx, vert in enumerate(mesh.vertices):
        state = points.get(str(idx))
        if state:
            vert.co.x = state.x
            vert.co.y = state.y

    mesh.update()
    return diag
