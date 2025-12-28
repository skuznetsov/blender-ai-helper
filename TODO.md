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
- [x] Constraint objects (Distance, Angle, H/V, Parallel, Perpendicular, Coincident, Radius, Midpoint, Equal Length, Concentric, Symmetry, Tangent, Fix).
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
- [x] Sketch Mode modal operator with command bar input.
  - Input formats: `x,y`, `@len<angle`, `dx,dy`.
  - DoD: user can draw line with numeric input.
  - [x] Axis lock toggle (X/Y) while drawing.
  - [x] Live length/angle preview while moving mouse.
  - [x] Angle snap toggle (Q) with configurable increment.
  - [x] Angle snap presets (15/30/45).
- [x] Precision coordinate edit for vertices (dialog).
  - DoD: selected vertex can be set to exact XY coordinates.
- [x] Precision edge length edit (dialog).
  - DoD: selected edge can be set to exact length.
- [x] Precision edge angle edit (dialog).
  - DoD: selected edge can be set to exact angle.
- [x] Snapping (grid, endpoints, midpoints, intersections) using quadtree.
  - DoD: snap selection is stable and predictable.
- [x] Constraint storage on sketch mesh + solver bridge.
  - DoD: constraints stored on sketch mesh and solver updates geometry.
- [x] Dimension overlay objects (length/angle/radius) with direct edit.
  - DoD: editing a dimension updates geometry via solver.
  - [x] Distance labels as text objects.
  - [x] Direct edit on labels (dialog).
  - [x] Angle labels + direct edit.
  - [x] Radius labels + direct edit.
- [x] Constraint UI (toggle per entity + auto-constraints on draw).
  - DoD: constraints appear and can be edited or removed.
  - [x] Manual add/edit/remove for distance/h/v/fix via panel.
  - [x] Angle constraint add/edit.
  - [x] Radius constraint add/edit.
  - [x] Coincident constraint add.
  - [x] Midpoint constraint add.
  - [x] Equal length constraint add.
  - [x] Concentric constraint add.
  - [x] Symmetry constraint add.
  - [x] Tangent constraint add.
  - [x] Parallel/Perpendicular constraints in panel.
  - [x] Auto-constraints on draw (horizontal/vertical).
  - [x] Constraint add dialogs prefill current values.
  - [x] Constraint diagnostics list.
  - [x] Select constraint geometry from list.
  - [x] Select worst constraint from diagnostics.
  - [x] Clear diagnostics button.
- [x] Circle tool + radius constraints.
  - DoD: circle can be added and radius constraints solve against it.

## 5) 3D ops (SAFE)
- [x] Extrude + Revolve operators (parametric, editable).
  - DoD: parameters can be adjusted after creation.
  - [x] Extrude via edge extrusion + stored params.
  - [x] Revolve via Screw modifier + stored params.
- [x] Rebuild policy: sketch is source of truth; 3D ops regenerate on change.
  - DoD: changes propagate reliably without corrupting mesh.
  - [x] Rebuild operator for extrude/revolve.
  - [x] Auto-rebuild on sketch edits.

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
- Constraint set parity (Fusion-like): tangent, equal, symmetry, midpoint, concentric implemented; needs Blender validation.
- Constraint diagnostics UI (highlight conflicting entities).
- History timeline for sketch edits.
- Parametric constraints on 3D ops (draft, shell, fillet).
- LLM: autogenerate constraints based on prompt.

## 9) Phase 2 features (CAUTION)
- [x] Parametric shell modifier for 3D ops.
  - DoD: Solidify modifier applied with stored params; rebuild preserves thickness.
- [x] Parametric fillet/bevel modifier for 3D ops.
  - DoD: Bevel modifier applied with stored params; rebuild preserves settings.
- [ ] Sketch history timeline (last N ops).
  - DoD: timeline UI lists ops; user can jump to previous state.
- [ ] LLM auto-constraints from prompt.
  - DoD: prompt yields constraint suggestions; preview & apply flow.
