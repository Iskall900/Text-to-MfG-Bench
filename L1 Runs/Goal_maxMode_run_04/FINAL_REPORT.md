# A15 bracket — final best-attempt report

## Outcome
**Not all requirements are met. The 10-modal-attempt user budget is exhausted.** The best completed candidate is **iteration9**, with identical CAD in iteration10. No further solver run was made after attempt 10. No hardware/CNC/environmental qualification is claimed.

### Selected deliverables
- Build123d source: `iteration9/geometry1/design_source.py` (run with `--wall 3.5` into a new destination).
- CAD: `iteration9/geometry1/bracket.step`, `.brep`, `.stl`.
- Preview: `iteration9/geometry1/bracket_front.png`, `bracket_rear.png`.
- Completed CalculiX input/log/results: `iteration9/FEA1/analysis.inp`, `solver.log`, `analysis.dat`, `analysis.frd`, `analysis_results.json`.
- Finer verification: `iteration10/FEA1/analysis_results.json`, `first_mode.png`, `mode1.npz`. This run timed out during later modal output, after all static cases and eigenvalues and first-mode output were written. Its first-mode and static data are usable diagnostics; clean job completion is **not** claimed.
- DfM/access checks and separate bolt/washer/head/insertion/driver STEP envelopes: `iteration9/DfM1/`.
- Machine-readable full status: `results_final.json`; run inventory: `run_ledger.json`.

## Numerical screening
Bracket-only CAD mass **198.386 g** (limit 200 g; density assumed 2700 kg/m³). One valid connected solid. Integral tapered plate/gusset tower, 3.5 mm nominal webs, 6 mm bearing plates, seven Ø6.8 mm holes; three original telescope hole axes and four original stage hole axes preserved. All reported bracket mass/stiffness excludes hardware, keep-outs and payload.

Completed first mode **171.153 Hz**; finer computed verification **170.888 Hz** (limit 100 Hz). Includes bracket density and **1.35 kg** MASS element at **(-1.6225, -57.164, 125.21) mm**. No rotary inertia invented. First mode is coupled payload rocking/translation and tower flexure/torsion. The payload translation eigenvector is approximately (0.231, 0.574, 0.785) in global XYZ, so Y-Z motion dominates; eigenvector sign and amplitude are arbitrary.

Finer static results, using **240 MPa assumed yield allowable**:

| Independent positive case | Max unaveraged Gauss von Mises MPa | Yield FoS | Max bracket displacement mm | Payload CG displacement magnitude mm |
|---|---:|---:|---:|---:|
| X | 41.89 | 5.73 | 0.03702 | 0.06728 |
| Y | 15.25 | 15.74 | 0.01871 | 0.01599 |
| Z | 9.55 | 25.14 | 0.01688 | 0.02078 |

The 1.4 yield FoS screening target is exceeded, conditional on assumed material and support properties. No support/notch stresses are excluded. Actual certified allowables across -40 to +85 C are unverified.

### Modeling evidence
CalculiX 2.20 through PATH `ccx`; C3D10 elements; N, mm, s, tonne units. E=68900 MPa, nu=0.33. Only T1/T2/T3 cylindrical bore nodes have fixed translations; no pad face or other material is fixed. A distributed least-squares remote connection uses 28 well-spread surface nodes per stage hole and exactly reproduces translation/rotation fields. It does not force stage-bore nodes into a rigid body. The point MASS node is independent in the corrected MPC equations. Each independent X=10g, Y=3g, Z=3g case applies force at the CG, transfers offset moments through the four holes, and includes same-signed bracket self-inertia. g=9.80665 m/s². Reversing an entire independent case negates linear stress/displacement/reactions while preserving von Mises and FoS; no additional negative-case solve was needed for this linear idealization.

Fine mesh: **123,468 bracket nodes**, **66,223 C3D10 elements**, plus one payload node and MASS element. Gmsh minimum scaled Jacobian 0.1315; minimum gamma 0.0241; all sampled minimum Jacobians positive. **Fine minimum gamma is below the chosen 0.05 threshold, so the fine mesh does not fully meet the mesh-quality criterion.** The completed iteration9 mesh passes both minimum gamma (0.0860) and scaled-Jacobian (0.1087) thresholds. Full distributions are in `mesh_and_model.json`.

Worst fine force-equilibrium error: **0.0176%**; worst moment-equilibrium error about global origin: **0.0078%**. These include CAD mass/centroid for self-inertia, hence small CAD/curved-mesh integration differences. Reactions and moments are explicitly retained in each result JSON.

### Convergence limitation
Iteration9 → iteration10: first frequency change 0.155%; displacements stable within 3%. **X maximum stress changes 11.69%**, exceeding the chosen 10% peak-stress criterion. Peak-stress convergence is therefore **not established** for the selected geometry, despite a large current yield margin. Iteration7 → iteration8 is a complete two-mesh pair with stress changes below 10%, frequency 169.701 Hz and mass 196.412 g, but iteration8 minimum gamma is only 0.00062; it is not a fully validated mesh-quality fallback. See `convergence.json`; do not confuse design changes with a same-geometry convergence test.

## Blocking keep-out contradiction
The literal user cylinder is centered **(79.4,19.5)** with radius **70 mm**, spanning **Z=-77.8 to +31.4 mm**. In A15 coordinates, required telescope axes at Z=0 are:
- T1 distance to cylinder axis **64.143 mm**, inside radius 70.
- T2 distance **54.275 mm**, inside radius 70. Even the full Ø24 mm T2 pad is inside this cylinder at the mounting plane.

The best bracket has **9278.654 mm³ literal cylinder overlap — FAIL.** A design preserving these mounting pads cannot avoid a keep-out that contains them. The image describes an upright setup rotated from STEP, but **no STEP file or STEP-to-A15 transform was supplied**. No arbitrary transform was invented. If the cylinder is truly in a distinct STEP frame, transformed clearance is **UNVERIFIED**, not a pass. Also, user prose says four mounting pads while A15 specifies exactly three telescope holes; no fourth bolt was invented.

**To close this blocker:** provide the STEP-to-A15 rigid transform (or the original STEP with named datum references), confirm the mounting-pad count and whether pad volumes are explicitly excepted from the cylinder. Then recheck clearance and rerun changed geometry in a new budget/session if needed.

## Manufacturing, assembly and unresolved requirements
The geometry is a one-piece 5-axis CNC billet concept with broad planar gussets and open rounded through-windows, not enclosed deep pockets or a network of cylindrical struts. Main window corners R3 mm, front windows R4 mm; standard clearance drills; pads Ø24 mm. Separate bracket-only head, screw insertion, driver, shank and washer envelope intersections pass for all seven interfaces, as do full assumed washer-bearing checks. Washer placement is separate from straight screw insertion. Actual NAS variants, lengths, thread engagement, preload, assembled telescope/stage/tool access, fastener strength and stiffness remain unverified.

Conservative stage and telescope envelope boxes are exported and their assumed extents documented. They are not substitutes for measured hardware. A separate optical path was not supplied. No detailed telescope or stage body was fabricated. CAM/holder reach, workholding, machining distortion, sharp web-junction finishing radii, material certification, full temperature behavior and defined MIL-STD-810G vibration/shock qualification remain unverified. A machinist review, CAM simulation, dimensional/weight inspection and physical structural/modal tests are needed before release.

## Run history (all preserved; no archive/deletion)
| Iteration | CAD mass g | First mode Hz | Minimum yield FoS | Invocation status |
|---|---:|---:|---:|---|
| iteration1 | 145.847 | unavailable | 0.475 | solver_failed_before_modal_step |
| iteration2 | 187.663 | 71.10911 | 1.398 | completed |
| iteration3 | 191.085 | 155.4769 | 3.046 | completed |
| iteration4 | 192.429 | 157.1153 | 2.876 | completed |
| iteration5 | 192.429 | 156.9254 | 2.500 | completed |
| iteration6 | 202.331 | 0.0 | 6.618 | rejected_multiple_solids_and_free_modes |
| iteration7 | 196.412 | 170.0098 | 6.307 | completed |
| iteration8 | 196.412 | 169.7011 | 5.792 | completed |
| iteration9 | 198.386 | 171.1534 | 6.488 | completed |
| iteration10 | 198.386 | 170.8879 | 5.730 | output_interrupted_after_eigensolution |

Exactly **10 modal-containing invocations** were made. Failed attempt 1 and interrupted attempt 10 count. One additional **static-only** diagnostic used no modal keyword. All source, CAD, meshes, inputs, outputs, solver diagnostics, previews and reports remain in their original iteration folders. Reference manuals were read from `/opt/docs`; attempted web search was unavailable, so no externally sourced/certified material properties are claimed.
