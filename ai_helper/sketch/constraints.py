from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class DistanceConstraint:
    id: str
    p1: str
    p2: str
    distance: float
    kind: str = field(init=False, default="distance")

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind,
            "p1": self.p1,
            "p2": self.p2,
            "distance": self.distance,
        }


@dataclass
class AngleConstraint:
    id: str
    p1: str
    vertex: str
    p2: str
    degrees: float
    kind: str = field(init=False, default="angle")

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind,
            "p1": self.p1,
            "vertex": self.vertex,
            "p2": self.p2,
            "degrees": self.degrees,
        }


@dataclass
class HorizontalConstraint:
    id: str
    line: str
    kind: str = field(init=False, default="horizontal")

    def to_dict(self) -> Dict[str, object]:
        return {"id": self.id, "kind": self.kind, "line": self.line}


@dataclass
class VerticalConstraint:
    id: str
    line: str
    kind: str = field(init=False, default="vertical")

    def to_dict(self) -> Dict[str, object]:
        return {"id": self.id, "kind": self.kind, "line": self.line}


@dataclass
class ParallelConstraint:
    id: str
    line_a: str
    line_b: str
    kind: str = field(init=False, default="parallel")

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind,
            "line_a": self.line_a,
            "line_b": self.line_b,
        }


@dataclass
class PerpendicularConstraint:
    id: str
    line_a: str
    line_b: str
    kind: str = field(init=False, default="perpendicular")

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind,
            "line_a": self.line_a,
            "line_b": self.line_b,
        }


@dataclass
class CoincidentConstraint:
    id: str
    p1: str
    p2: str
    kind: str = field(init=False, default="coincident")

    def to_dict(self) -> Dict[str, object]:
        return {"id": self.id, "kind": self.kind, "p1": self.p1, "p2": self.p2}


@dataclass
class ConcentricConstraint:
    id: str
    p1: str
    p2: str
    kind: str = field(init=False, default="concentric")

    def to_dict(self) -> Dict[str, object]:
        return {"id": self.id, "kind": self.kind, "p1": self.p1, "p2": self.p2}


@dataclass
class SymmetryConstraint:
    id: str
    line: str
    p1: str
    p2: str
    kind: str = field(init=False, default="symmetry")

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind,
            "line": self.line,
            "p1": self.p1,
            "p2": self.p2,
        }


@dataclass
class TangentConstraint:
    id: str
    line: str
    circle: str
    center: str
    radius: float
    kind: str = field(init=False, default="tangent")

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind,
            "line": self.line,
            "circle": self.circle,
            "center": self.center,
            "radius": self.radius,
        }


@dataclass
class MidpointConstraint:
    id: str
    line: str
    point: str
    kind: str = field(init=False, default="midpoint")

    def to_dict(self) -> Dict[str, object]:
        return {"id": self.id, "kind": self.kind, "line": self.line, "point": self.point}


@dataclass
class EqualLengthConstraint:
    id: str
    line_a: str
    line_b: str
    kind: str = field(init=False, default="equal_length")

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind,
            "line_a": self.line_a,
            "line_b": self.line_b,
        }


@dataclass
class RadiusConstraint:
    id: str
    entity: str
    radius: float
    kind: str = field(init=False, default="radius")

    def to_dict(self) -> Dict[str, object]:
        return {"id": self.id, "kind": self.kind, "entity": self.entity, "radius": self.radius}


@dataclass
class FixConstraint:
    id: str
    point: str
    kind: str = field(init=False, default="fix")

    def to_dict(self) -> Dict[str, object]:
        return {"id": self.id, "kind": self.kind, "point": self.point}


SketchConstraint = (
    DistanceConstraint
    | AngleConstraint
    | HorizontalConstraint
    | VerticalConstraint
    | ParallelConstraint
    | PerpendicularConstraint
    | CoincidentConstraint
    | ConcentricConstraint
    | SymmetryConstraint
    | TangentConstraint
    | MidpointConstraint
    | EqualLengthConstraint
    | RadiusConstraint
    | FixConstraint
)


def constraint_from_dict(data: Dict[str, object]) -> SketchConstraint:
    kind = data.get("kind")
    if kind == "distance":
        return DistanceConstraint(
            id=str(data["id"]),
            p1=str(data["p1"]),
            p2=str(data["p2"]),
            distance=float(data["distance"]),
        )
    if kind == "angle":
        return AngleConstraint(
            id=str(data["id"]),
            p1=str(data["p1"]),
            vertex=str(data["vertex"]),
            p2=str(data["p2"]),
            degrees=float(data["degrees"]),
        )
    if kind == "horizontal":
        return HorizontalConstraint(id=str(data["id"]), line=str(data["line"]))
    if kind == "vertical":
        return VerticalConstraint(id=str(data["id"]), line=str(data["line"]))
    if kind == "parallel":
        return ParallelConstraint(
            id=str(data["id"]),
            line_a=str(data["line_a"]),
            line_b=str(data["line_b"]),
        )
    if kind == "perpendicular":
        return PerpendicularConstraint(
            id=str(data["id"]),
            line_a=str(data["line_a"]),
            line_b=str(data["line_b"]),
        )
    if kind == "coincident":
        return CoincidentConstraint(
            id=str(data["id"]),
            p1=str(data["p1"]),
            p2=str(data["p2"]),
        )
    if kind == "concentric":
        return ConcentricConstraint(
            id=str(data["id"]),
            p1=str(data["p1"]),
            p2=str(data["p2"]),
        )
    if kind == "symmetry":
        return SymmetryConstraint(
            id=str(data["id"]),
            line=str(data["line"]),
            p1=str(data["p1"]),
            p2=str(data["p2"]),
        )
    if kind == "tangent":
        return TangentConstraint(
            id=str(data["id"]),
            line=str(data["line"]),
            circle=str(data["circle"]),
            center=str(data["center"]),
            radius=float(data["radius"]),
        )
    if kind == "midpoint":
        return MidpointConstraint(
            id=str(data["id"]),
            line=str(data["line"]),
            point=str(data["point"]),
        )
    if kind == "equal_length":
        return EqualLengthConstraint(
            id=str(data["id"]),
            line_a=str(data["line_a"]),
            line_b=str(data["line_b"]),
        )
    if kind == "radius":
        return RadiusConstraint(
            id=str(data["id"]),
            entity=str(data["entity"]),
            radius=float(data["radius"]),
        )
    if kind == "fix":
        return FixConstraint(id=str(data["id"]), point=str(data["point"]))
    raise ValueError(f"Unknown constraint kind: {kind}")


def constraints_to_dict(constraints: List[SketchConstraint]) -> List[Dict[str, object]]:
    return [c.to_dict() for c in constraints]
