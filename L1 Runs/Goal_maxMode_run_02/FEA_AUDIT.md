# Run 02 FEA audit

Reviewed generated iteration 7 geometry, meshing script, actual CalculiX input, solver log, mesh metadata and static/modal output, against A15.json and prompt.txt. This is a file-based audit; no additional solves were run and the modal budget was not reset.

## Verdict

A real supported modal analysis ran with internally consistent units and the specified payload mass at its CG. The 85.75219 Hz result is a result of this particular idealized model, not a mesh-converged or hardware-validated prediction. Do not certify compliance from it.

## Correct pieces verified

- mm–N–s units imply tonne mass units: E=68900 N/mm2, nu=0.33, density=2.7e-9 tonne/mm3, payload=1.35e-3 tonne (1.35 kg).
- Payload reference node is at (-1.6225,-57.164,125.21) mm, the A15 CG, connected to the stage-hole nodes. No invented payload rotational inertia tensor is present, consistent with A15's point-mass requirement.
- T1/T2/T3 translations are fixed; stage holes are coupled, not grounded. Checked node sets against exterior tetrahedral faces: all selected T and S nodes lie on the mesh boundary, and mounting-hole radius error is below 0.000001 mm.
- Bracket density and solid section are assigned. Integrated tetrahedron volume gives 197.3569 g versus CAD 197.2656 g (about 0.046% difference). Mass agreement does not establish stiffness convergence.
- Frequency is the first step, before static loading; it is an unprestressed supported solve, extracting 10 modes. Solver finished and saved mode shapes.
- Static loads reset with OP=NEW, use the prescribed accelerations/forces, and include bracket self-inertia. For iteration 7, summed support reactions balance expected force to output-rounding accuracy. X reversed case gives opposite reactions and equal peak von Mises stress. Full moment equilibrium was not independently recomputed.

## Must resolve before another benchmark

1. Keep-out coordinates: the agent applies z_setup=z_step+81.11 only to the obstruction, changing prompt's -77.8..31.4 range to 3.31..112.51 while retaining A15 mounting coordinates. The script states this assumption but does not establish it from reference geometry. A literal common-coordinate interpretation is not followed. Define one coordinate system or provide the measured reference transform before launch.
2. Stage side: stage plate occupies Y=-15.164..-7.164, negative Y of the mounting plane. A15 says stage side negative Y, stage structure primarily positive Y. The model puts supporting material on the stated stage side. Exact hole positions alone do not establish correct mating-side clearance.
3. Mesh: iteration 7 uses 78,689 C3D4 linear tetrahedra with no same-geometry mesh-refinement or higher-order comparison. Thin web/bending stiffness is not validated. CalculiX 2.20 manual section 6.2.6 warns C3D4 is overly stiff and recommends C3D10. No numerical error bound can be assigned to 85.75 Hz from this run.
4. Connection idealization: a single *RIGID BODY contains all 464 stage-hole nodes. It transfers the CG load, but also prevents relative movement/deformation among the four hole surfaces. This assumes a rigid stage interface and may stiffen the bracket. Fully fixing mounting bores likewise assumes rigid support rather than a modeled bolted joint. Neither is automatically a solver error; document and approve these assumptions, or use a justified alternative with sensitivity checks. Do not add arbitrary payload rotational inertia.
5. Enforcement: the prompt asks for 10 geometries and 10 modal attempts; image hard cap remains 30, and agent reached geometry 11 with only nine modal attempts. The operator setup did not enforce the geometry ceiling before execution. Iteration 9 has only static results; some geometry files were regenerated within the same iteration, losing their earlier versions. Use a run-specific hard modal cap plus immutable geometry snapshots and a pre-execution iteration check. A periodic notification heartbeat is not enforcement.

## Other findings and next-run changes

- Separate optimization solves from acceptance validation. Freeze one checked analysis template so the agent changes geometry rather than rewriting physics each time. Confirm CG mass, support sets, connectedness, units and geometry requirements automatically before solving.
- Set an explicit total modal budget and reserve some of it for same-geometry C3D10/refinement comparisons. Define convergence tolerance in advance (for example 2% first-frequency change as a chosen policy, not an existing requirement). Count failed attempts and validation solves.
- Produce one result JSON per iteration with geometry hash, CAD/mesh mass, modal frequency, stresses, reactions, equilibrium residuals, support/coupling assumptions and pass/fail/unknown. Prevent a new iteration until the prior record is complete or explicitly failed.
- Material stiffness/density values are plausible but sources and allowable yield stress were not supplied in the final result. Peak static stresses were 62.511 MPa for X+/X-, 56.814 MPa for Y+, and 44.269 MPa for Z+ on iteration 7. These are unconverged integration-point values; no certified factor of safety follows without a sourced allowable and chosen stress evaluation rule.
- Each modal input also repeats four static cases already run separately. Avoid this duplicate computation; do not eliminate the required independent static evaluations.
- Sparse IDs 999999/999998 cause the solver to estimate arrays for roughly one million nodes/elements despite about 21,000 physical nodes and 79,000 tets. Use consecutive IDs after the real mesh; this is efficiency, not proof of wrong results.
- Solver logs report one CPU for assembly/factorization. Hardware recommendations describe this mostly serial configuration, not a tuned parallel solver.
- The frequency-interval warning says 10 extracted modes do not cover all modes through 5000 Hz; it does not by itself invalidate the first mode. The MASS elastic-constant warning is not by itself evidence that the point mass was ignored.
- Monitoring captured resources but iteration notices were batched and the run was force-stopped, preventing normal final metering. Prefer solver/iteration completion events, graceful budget exhaustion and preserved provider usage, rather than relying on periodic chat wakeups.

Source: official CalculiX 2.20 manual, https://www.dhondt.de/ccx_2.20.pdf (sections on C3D4/C3D10, MASS, RIGID BODY, load reset and units).

Not checked: rerun validation, C3D10 convergence, physical bolt/contact stiffness, CAD boolean overlap under the literal prompt envelope, full moment equilibrium, CNC tool access or actual hardware.
