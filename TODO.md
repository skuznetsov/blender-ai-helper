# TODO

Legend: [ ] TODO | [~] IN_PROGRESS | [x] DONE

## 0) Project bootstrap (SAFE)
- [x] Create TODO.md (project plan).
- [x] Create Blender add-on scaffold (bl_info, register/unregister, basic panel).
  - DoD: add-on loads without errors; panel visible in 3D View > N-panel.
  - Fallback: `python3 -m py_compile` on add-on modules.
- [x] Define config + logging (addon name, version, debug toggle).
  - DoD: config values exposed in Preferences panel.

## 1) Sketch data model (SAFE)
- [x] Data structures for sketch entities (Point, Line, Arc, Circle, Polyline).
  - DoD: unit tests or demo script that creates entities and serializes them.
- [x] Constraint objects (Distance, Angle, H/V, Parallel, Perpendicular, Coincident, Radius, Fix).
  - DoD: constraints can be created/serialized and validated.

## 2) Solver MVP (SAFE)
- [x] PBD / Gauss-Seidel solver core (iterative projection) with time budget.
  - DoD: synthetic sketch converges within tolerance in <10ms for 100 constraints.
- [x] Conflict handling policy (detect non-convergence + constraint diagnostics).
  - DoD: conflicting constraints produce readable error + soft fallback.
- [x] Optional DG relax (distance-only) as a pre-solve step.
  - DoD: toggled relax improves convergence on bad initial states.

## 3) Spatial indexing (SAFE)
- [x] Quadtree for 2D snapping and nearest queries.
  - DoD: query_radius / nearest returns correct points in tests.

## 4) Sketch UX (CAUTION)
- [~] Sketch Mode modal operator with command bar input.
  - Input formats: `x,y`, `@len<angle`, `dx,dy`.
  - DoD: user can draw line with numeric input.
- [ ] Snapping (grid, endpoints, midpoints, intersections) using quadtree.
  - DoD: snap selection is stable and predictable.
- [ ] Dimension overlay objects (length/angle/radius) with direct edit.
  - DoD: editing a dimension updates geometry via solver.
- [ ] Constraint UI (toggle per entity + auto-constraints on draw).
  - DoD: constraints appear and can be edited or removed.

## 5) 3D ops (SAFE)
- [ ] Extrude + Revolve operators (parametric, editable).
  - DoD: parameters can be adjusted after creation.
- [ ] Rebuild policy: sketch is source of truth; 3D ops regenerate on change.
  - DoD: changes propagate reliably without corrupting mesh.

## 6) LLM integration (SAFE)
- [x] Selection serializer (compact summary, units, bbox, counts).
  - DoD: summary fits in small token budget; no raw mesh dumps.
- [x] Grok client adapter (wrap ../../ML/agents_assembly/llm_interfaces/grok.py).
  - DoD: mock call returns structured function calls.
- [x] Function dispatcher with preview/apply flow + undo safety.
  - DoD: operations are previewed before apply; undo works.

## 7) Performance & stability (SAFE)
- [x] Frame time budget for solver; early exit on low error.
  - DoD: keeps UI responsive under 200 constraints.
- [x] Stress tests on 500+ constraints.
  - DoD: no crashes; clear warnings on limits.

## 8) Documentation (SAFE)
- [x] Quick-start guide + UX cheat sheet (inputs, constraints, modes).
  - DoD: new user can draw lines and preview tool calls in <10 minutes.
- [x] Architecture notes (solver, data flow, LLM safety).
  - DoD: explains rebuild and conflict policy.

## Ideas backlog
- Full constraint set (Fusion-like): tangent, equal, symmetry, midpoint, concentric.
- Constraint diagnostics UI (highlight conflicting entities).
- History timeline for sketch edits.
- Parametric constraints on 3D ops (draft, shell, fillet).
- LLM: autogenerate constraints based on prompt.
