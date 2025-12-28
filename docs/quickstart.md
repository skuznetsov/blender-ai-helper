# Quick Start

## Install
1. Open Blender 5.0.
2. Edit > Preferences > Add-ons > Install.
3. Select the `ai_helper` folder from this repo.
4. Enable the add-on.

## LLM Preview
1. Open View3D > Sidebar > AI Helper.
2. Enter a prompt (optionally add Image Path/URL + Notes).
3. (Optional) Pick a preset and click Use/Append, or Params for custom sizes (plate, bracket, slot, frame, bolt circle, slot pair).
4. (Optional) Pick a recipe for common LLM workflows and click Use/Append.
5. Click Preview to generate tool calls.
6. Inspect the preview and click Apply.
7. For constraints, select sketch geometry and ask for a constraint (e.g., "add horizontal constraint").
8. For sketch generation, describe the geometry or attach an image and notes (uses add_line/add_circle/add_arc/add_polyline/add_rectangle tool calls).

## Sketch (WIP)
- Sketch Mode creates line segments on the XY plane.
- Click to set a start point, then type `x,y` and press Enter.
- Default mode is REL; press Tab to toggle ABS/REL or prefix `=` for absolute.
- Polar input: `@len<angle` (degrees).
- Press A to toggle auto constraints; press S to toggle snapping; press Q to toggle angle snap; hold Shift to temporarily disable snapping.
- Axis lock: press X or Y to lock movement to the axis (press again to clear).
- Live preview: header shows length and angle while moving the mouse.
- Angle snap presets: use 15/30/45 buttons in Sketch Settings.
- Add Circle: click Add Circle and enter center/radius in the dialog (defaults to 3D cursor).
- Add Arc: click Add Arc and enter center/radius/start/end angle.
- Add Rectangle: click Add Rectangle and enter center/width/height (optional rotation).
- Add Polyline: click Add Polyline and enter points as `x,y; x,y; x,y`.
- Constraints: select edges or vertices, then use the Constraints panel to add Distance/Horizontal/Vertical/Angle/Radius/Coincident/Midpoint/Equal Length/Concentric/Symmetry/Tangent/Parallel/Perpendicular/Fix.
- Inspector: select a vertex/edge/arc/rectangle and edit numeric values in the Inspector panel.
- Angle constraints: select two connected edges and set the target angle.
- Radius constraints: select a circle vertex or edge to attach a radius.
- Midpoint constraint: select an edge and a vertex to force the vertex to the edge midpoint.
- Equal Length: select two edges to force them to equal length.
- Concentric: select two circles to force the same center.
- Symmetry: select an edge and two vertices to mirror them across the edge.
- Tangent: select an edge and a circle to make them tangent.
- Precision edit: select a vertex and use Set Vertex Coords to enter exact coordinates.
- Precision edit: select an edge and use Set Edge Length to set its exact length.
- Precision edit: select an edge and use Set Edge Angle to set its angle.
- Precision edit: select an arc edge and use Edit Arc to change center/radius/angles (LLM can call edit_arc too).
- Precision edit: select a rectangle edge and use Edit Rectangle to change size/center/rotation (LLM can call edit_rectangle too).
- Dimensions: use Update Dimensions to create text labels for distance, angle, and radius constraints.
- Constraint list: use Sel to highlight the geometry for a constraint.
- Tags: use the Tags panel to select tagged sketch geometry created by LLM prompts.
- Diagnostics: use Select Worst to jump to the largest error after solve.
- Diagnostics: use Clear Diagnostics to reset the report panel.
- Dimension edit: select a label and use Edit Selected Dimension to update the value.
- 3D ops: use Extrude Sketch or Revolve Sketch, then Rebuild 3D Ops if the sketch changes.
- Extrude uses selected sketch edges when available (toggle via the Use Selection option).
- Loft: tag two profile edge sets and run Loft Profiles (use Offset Z if profiles are coplanar).
- Multi-loft: provide a comma-separated Profile Tags list (3+ tags) in the Loft Profiles operator.
- Sweep: tag profile edges and a path polyline (or select closed profile + open path edges), then run Sweep Profile (profile follows path with optional twist).
- 3D modifiers: select a 3D op object and use Add Shell or Add Fillet to apply Solidify/Bevel.
- History: use Capture Snapshot and Restore in the History panel to jump between steps.
- Auto rebuild: toggle Auto Rebuild 3D Ops in the 3D Ops panel.

## Notes
- The LLM adapter defaults to mock mode unless a Grok adapter path is set.
- Large mesh data is not sent to the LLM; only selection summaries.
- Image payloads are capped at 2MB in the adapter.
- Grok vision accepts HTTPS image URLs; local file paths may require hosting or a provider that supports data URLs.
- Grok 4.1 Fast Reasoning supports PNG/JPEG data URLs up to 20MB when used as the vision model.
- If data URL fails with decode errors, try JPEG or an HTTPS URL instead.
- Default vision model is `grok-4-1-fast-reasoning`.
- You can set Grok model ids and a default vision image URL in Preferences.
- If Grok preview fails with `aiohttp` missing, use Preferences > Install aiohttp or run `blender_python -m pip install aiohttp`.
- For local images, set a Vision Upload Command in Preferences (must print an HTTPS URL; supports `{path}`/`{abs_path}`).
- If a data URL fails to decode, the adapter automatically retries using the Vision Upload Command (when set).
- For the smoke test script, set `GROK_VISION_USE_DATA_URL=1` to force data URL mode.
