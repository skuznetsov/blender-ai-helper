from ai_helper.sketch.entities import Sketch, Vec2
from ai_helper.sketch.constraints import DistanceConstraint


def main() -> None:
    sketch = Sketch()
    p1 = sketch.add_point(Vec2(0.0, 0.0))
    p2 = sketch.add_point(Vec2(2.0, 0.0))
    sketch.add_line(p1, p2)

    constraints = [DistanceConstraint(id="c1", p1=p1, p2=p2, distance=2.0)]

    payload = {"sketch": sketch.to_dict(), "constraints": [c.to_dict() for c in constraints]}
    restored = Sketch.from_dict(payload["sketch"])

    assert len(restored.points) == 2
    assert len(restored.entities) == 1


if __name__ == "__main__":
    main()
