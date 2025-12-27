# Quick Start

## Install
1. Open Blender 5.0.
2. Edit > Preferences > Add-ons > Install.
3. Select the `ai_helper` folder from this repo.
4. Enable the add-on.

## LLM Preview
1. Open View3D > Sidebar > AI Helper.
2. Enter a prompt.
3. Click Preview to generate tool calls.
4. Inspect the preview and click Apply.

## Sketch (WIP)
- Sketch Mode creates line segments on the XY plane.
- Click to set a start point, then type `x,y` and press Enter.
- Default mode is REL; press Tab to toggle ABS/REL or prefix `=` for absolute.
- Polar input: `@len<angle` (degrees).
- Press A to toggle auto constraints; press S to toggle snapping; hold Shift to temporarily disable snapping.
- Axis lock: press X or Y to lock movement to the axis (press again to clear).
- Add Circle: click Add Circle and enter center/radius in the dialog (defaults to 3D cursor).
- Constraints: select edges or vertices, then use the Constraints panel to add Distance/Horizontal/Vertical/Angle/Radius/Coincident/Midpoint/Equal Length/Concentric/Symmetry/Tangent/Parallel/Perpendicular/Fix.
- Angle constraints: select two connected edges and set the target angle.
- Radius constraints: select a circle vertex or edge to attach a radius.
- Midpoint constraint: select an edge and a vertex to force the vertex to the edge midpoint.
- Equal Length: select two edges to force them to equal length.
- Concentric: select two circles to force the same center.
- Symmetry: select an edge and two vertices to mirror them across the edge.
- Tangent: select an edge and a circle to make them tangent.
- Precision edit: select a vertex and use Set Vertex Coords to enter exact coordinates.
- Dimensions: use Update Dimensions to create text labels for distance, angle, and radius constraints.
- Constraint list: use Sel to highlight the geometry for a constraint.
- Diagnostics: use Select Worst to jump to the largest error after solve.
- Diagnostics: use Clear Diagnostics to reset the report panel.
- Dimension edit: select a label and use Edit Selected Dimension to update the value.
- 3D ops: use Extrude Sketch or Revolve Sketch, then Rebuild 3D Ops if the sketch changes.
- Auto rebuild: toggle Auto Rebuild 3D Ops in the 3D Ops panel.

## Notes
- The LLM adapter defaults to mock mode unless a Grok adapter path is set.
- Large mesh data is not sent to the LLM; only selection summaries.
