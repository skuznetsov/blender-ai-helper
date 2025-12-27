# Architecture Notes

## Sketch Core
- Entities: points, lines, arcs, circles, polylines.
- Constraints: distance, angle, horizontal/vertical, parallel/perpendicular, coincident, radius, fix.
- Solver: PBD/Gauss-Seidel with time budget; supports soft fallback on conflicts.

## LLM Flow
1. Serialize selection summary (units, transforms, counts).
2. Send prompt + summary to Grok adapter.
3. Parse tool calls and show preview.
4. Apply tool calls with undo push.

## Safety
- No raw mesh data in prompts.
- Preview is required before apply.
- Soft fallback drops worst constraint if solver does not converge.

## Rebuild Policy (planned)
- Sketch is source of truth for 3D ops.
- 3D operations regenerate on sketch changes.
  - Auto rebuild uses depsgraph handler and can be disabled via UI.

## 3D Ops (MVP)
- Extrude: duplicate sketch mesh and extrude edges along Z.
- Revolve: Screw modifier around Z axis with angle + steps params.
