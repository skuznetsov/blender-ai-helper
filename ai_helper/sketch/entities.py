from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Dict, List


def new_id() -> str:
    return uuid.uuid4().hex


@dataclass(frozen=True)
class Vec2:
    x: float
    y: float

    def to_dict(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "Vec2":
        return cls(float(data["x"]), float(data["y"]))


@dataclass
class SketchPoint:
    id: str
    pos: Vec2
    locked: bool = False

    def to_dict(self) -> Dict[str, object]:
        return {"id": self.id, "pos": self.pos.to_dict(), "locked": self.locked}

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "SketchPoint":
        return cls(
            id=str(data["id"]),
            pos=Vec2.from_dict(data["pos"]),
            locked=bool(data.get("locked", False)),
        )


@dataclass
class Line:
    id: str
    p1: str
    p2: str
    kind: str = field(init=False, default="line")

    def to_dict(self) -> Dict[str, object]:
        return {"id": self.id, "kind": self.kind, "p1": self.p1, "p2": self.p2}


@dataclass
class Arc:
    id: str
    center: str
    start: str
    end: str
    clockwise: bool = False
    kind: str = field(init=False, default="arc")

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind,
            "center": self.center,
            "start": self.start,
            "end": self.end,
            "clockwise": self.clockwise,
        }


@dataclass
class Circle:
    id: str
    center: str
    radius: float
    kind: str = field(init=False, default="circle")

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind,
            "center": self.center,
            "radius": self.radius,
        }


@dataclass
class Polyline:
    id: str
    points: List[str]
    closed: bool = False
    kind: str = field(init=False, default="polyline")

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind,
            "points": list(self.points),
            "closed": self.closed,
        }


SketchEntity = Line | Arc | Circle | Polyline


def entity_from_dict(data: Dict[str, object]) -> SketchEntity:
    kind = data.get("kind")
    if kind == "line":
        return Line(id=str(data["id"]), p1=str(data["p1"]), p2=str(data["p2"]))
    if kind == "arc":
        return Arc(
            id=str(data["id"]),
            center=str(data["center"]),
            start=str(data["start"]),
            end=str(data["end"]),
            clockwise=bool(data.get("clockwise", False)),
        )
    if kind == "circle":
        return Circle(
            id=str(data["id"]),
            center=str(data["center"]),
            radius=float(data["radius"]),
        )
    if kind == "polyline":
        return Polyline(
            id=str(data["id"]),
            points=[str(pid) for pid in data.get("points", [])],
            closed=bool(data.get("closed", False)),
        )
    raise ValueError(f"Unknown entity kind: {kind}")


@dataclass
class Sketch:
    points: Dict[str, SketchPoint] = field(default_factory=dict)
    entities: List[SketchEntity] = field(default_factory=list)

    def add_point(self, pos: Vec2, locked: bool = False) -> str:
        pid = new_id()
        self.points[pid] = SketchPoint(id=pid, pos=pos, locked=locked)
        return pid

    def add_line(self, p1: str, p2: str) -> Line:
        line = Line(id=new_id(), p1=p1, p2=p2)
        self.entities.append(line)
        return line

    def to_dict(self) -> Dict[str, object]:
        return {
            "points": [p.to_dict() for p in self.points.values()],
            "entities": [e.to_dict() for e in self.entities],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "Sketch":
        points = {}
        for p in data.get("points", []):
            sp = SketchPoint.from_dict(p)
            points[sp.id] = sp
        entities = [entity_from_dict(e) for e in data.get("entities", [])]
        return cls(points=points, entities=entities)
