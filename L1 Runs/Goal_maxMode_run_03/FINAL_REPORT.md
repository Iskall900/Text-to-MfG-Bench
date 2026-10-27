# A15 bracket — best attempt, NOT an all-requirements-compliant release

## Outcome

The **10/10 modal CalculiX invocation budget is exhausted** (failed attempts 1 and 2 count). Best deliverable: **iteration10**, byte-identical CAD to valid iteration8 and iteration9. No hardware or CNC qualification is claimed.

- Build123d solid: [STEP](iteration10/geometry1/bracket.step), [BREP](iteration10/geometry1/bracket.brep), [STL](iteration10/geometry1/bracket.stl).
- Exact valid source: [build123d_source_final.py](iteration10/geometry1/build123d_source_final.py). Earlier failed implementation sources remain present and are not the selected source.
- [Geometry preview](iteration10/geometry1/bracket_preview.png), [first mode](iteration10/FEA1/model_complete/first_mode.png), [machine-readable results](results_final.json).
- Nominal bracket-only CAD mass **189.532 g** (limit 200 g); one valid connected solid.
- Supported first mode including 1.35 kg offset payload: **143.0968 Hz** (target ≥100 Hz).
- Minimum final-mesh nominal yield FoS: **5.017** (target ≥1.4). These are model-level screening results, not a qualified strength claim.

## Blocking keep-out conflict

The requested cylinder was modeled **exactly as supplied**, center (79.4,19.5), radius70, Z=−77.8…31.4 mm. No undocumented rotation or translation was invented. A15 uses the JSON/setup frame; the user calls the cylinder frame the original STEP frame, and the image says STEP was rotated upright. **No original STEP or STEP-to-setup rigid transform was provided.**

If the numerical coordinates are interpreted directly in one frame:

| Telescope interface at Z=0 | Radial distance from cylinder axis | Inside R70? |
|---|---:|---|
| T1 | 64.1428 mm | yes, by 5.8572 mm |
| T2 | 54.2749 mm | yes, by 15.7251 mm |
| T3 | 140.0864 mm | no |

Thus the normal quarter-inch bores and their bearing material at T1/T2 conflict with the exclusion volume. The complete T2 Ø24 pad is inside R70 and inside its Z range. The selected candidate has **7046.063 mm³ direct-coordinate keep-out overlap**, so **it does not pass this check**. Cutting away that volume would destroy the retained mounting interfaces; no such misleading modification was made. See [conflict diagram](iteration10/geometry1/keepout_conflict.png) and the separate keep-out STEP.

**Needed:** the original registered STEP and its rigid transform into A15 coordinates, or corrected cylinder coordinates / an explicit permitted mounting-pad exception. If direct registration is intended without exceptions, this mounting arrangement and keep-out are incompatible.

## Geometry and interface definition

Six nominal Ø10 round load-path members connect three Ø24 × 6 mm telescope pads to a 7 mm thick stage frame. The frame is a 44.4 mm rounded square with a 12 mm rounded central opening. Bracket volume 70196.9105 mm³. Nominal bounding box: X −70.86…42.03, Y −33.45…54.047, Z 0…151 mm. The stage-facing plane remains Y=−7.164; stage lies toward −Y and the upper structure is primarily toward +Y.

All T1–T3 and S1–S4 centers and axes are taken directly from A15, with nominal Ø6.6 mm clearance bores. T mounting plane Z=0 and S mounting plane Y=−7.164 are preserved. The JSON CG (−1.6225,−57.164,125.21) mm takes precedence over the image's rounded 125.206 mm Z annotation. No production tolerance was supplied; this is nominal CAD preservation, not measured compatibility.

## CalculiX model and assumptions

- CalculiX 2.20 invoked exclusively as `ccx` through PATH. C3D10 quadratic solid elements; Gmsh's last two edge nodes are explicitly reordered for CalculiX.
- N–mm–s–tonne consistent units. Assumed 6061-T651 properties: E=68,900 MPa, ν=0.33, ρ=2.7e−9 tonne/mm³ (2700 kg/m³), yield allowable=240 MPa. These are engineering assumptions, **not certified lot/thickness/temperature data**. No external material source was successfully retrieved (web search service unavailable); cached manuals document software, not alloy allowables.
- All three translational DOFs fixed **only on the cylindrical T1/T2/T3 bore nodes**. No pad faces, strut nodes or stage holes fixed. This is the user's idealized fixed-bore support model, not a validation of real bolt/joint stiffness, preload, slip or opening.
- Exactly one 0.00135 tonne point mass at the JSON CG. No invented intrinsic payload rotational inertia. Offset inertia arises only from this point mass and its kinematic lever arm.
- Non-rigidifying distributed remote relation: least-squares rigid-motion reconstruction from 24 real nodes per stage bore (96 total), equal total weight per bolt, then evaluate CG translation 50 mm outward. This constrains only three CG translations; it does **not** make the bore surfaces rigid. Three surface DOFs are algebraic pivots so the CalculiX MASS node remains independent. Rigid-motion reproduction error 2.13e-14.
- Static forces use the transpose of the same map, preserving resultant force and offset moment. Bracket self-inertia uses the consistent quadratic-element mass integral. No payload/reference/hardware is added to bracket-only mass or stiffness.
- Independent +X 10g, +Y 3g, +Z 3g cases, g=9.80665 m/s²; payload forces 132.389775 / 39.7169325 / 39.7169325 N, plus bracket inertia in the same signed direction. Signs were unresolved in A15, so + signs were chosen. In this linear elastic, bilateral-support model, reversing a case reverses stress/displacement/reactions and preserves von Mises and FoS. This equivalence is not asserted for real nonlinear joints.

## Finest-mesh static results

Stress metric: maximum **unaveraged integration-point von Mises over the entire bracket**, with no bore or root exclusion. Yield FoS=240 MPa/evaluated stress. Displacements include the remote CG; no displacement acceptance limit exists in A15.

| Case | Max stress MPa | Nominal yield FoS | Max displacement mm | Relative force error | Relative moment error |
|---|---:|---:|---:|---:|---:|
| X | 47.837 | 5.017 | 0.082468 | 2.75e-08 | 1.80e-08 |
| Y | 12.031 | 19.949 | 0.022993 | 7.89e-08 | 1.30e-08 |
| Z | 17.061 | 14.067 | 0.030748 | 6.41e-08 | 2.46e-08 |

Per-bolt forces/moments, CG displacement vectors, global reaction sums and applied resultants are in [results.json](iteration10/FEA1/model_complete/results.json). Reactions subtract applied consistent self-inertia loads at restrained nodes from CalculiX's reported external nodal forces. The moment balance is evaluated about the global origin. All balance checks pass the adopted 0.5% screen.

## Mesh quality and convergence

Final mesh: **127443 C3D10** plus one MASS element; **213553 solid nodes**, 213554 including CG. Minimum SICN 0.100119; 1st percentile 0.574626; all sampled quadratic Jacobians positive (minimum determinant 0.00383614). Adopted mesh screen: minSICN>0.05 and positive sampled Jacobians. Both pass. CAD-to-final-mesh mass difference is 0.00287%.

The following meshes have **byte-identical STEP geometry** and each passes the mesh-quality screen:

| Verification iteration | Elements | Solid nodes | First frequency Hz | Peak stress X / Y / Z MPa |
|---|---:|---:|---:|---|
| 8 | 54469 | 96319 | 143.4695 | 48.059 / 12.224 / 17.206 |
| 9 | 72472 | 125582 | 143.2958 | 41.090 / 12.020 / 16.180 |
| 10 | 127443 | 213553 | 143.0968 | 47.837 / 12.031 / 17.061 |

Adopted convergence screens (A15 leaves criteria null): ≤2% first-frequency change, ≤5% displacement change, ≤10% peak-stress change between the finest two meshes. Frequency changes **0.1391%**, passing. Displacements pass. Peak-stress changes X/Y/Z are **14.11% / 0.09% / 5.16%**. **X peak-stress convergence fails the 10% screen**; oscillatory root/relief-edge peaks are not hidden by nodal averaging or selective exclusion. The lowest nominal FoS across accepted meshes of the final geometry is 4.994, but fully verified strength remains unestablished. See [convergence.json](iteration10/FEA1/convergence.json).

First mode vectors are supplied as CSV and NPZ, including the reconstructed CG vector. PNG deformation is exaggerated and has arbitrary eigenvector sign, not a physical displacement prediction.

## DfM, hardware and other clearances

[DfM report](iteration10/DfM1/DFM_REPORT.md). All 35 separately exported assumed bolt/washer/head/insertion/driver envelopes clear the bracket itself. Each of seven assumed OD16/ID6.6 washers has its entire 166.850 mm² annulus supported. This does **not** establish actual NAS620/NAS1352 compatibility: washer/head dimensions, lengths, engagement, driver and assembly directions require confirmation.

Conservative assumption envelopes: stage 60×100×60 mm, X −31.6225…28.3775, Y −107.164…−7.164, Z 95.21…155.21; telescope half-space represented by a large block below Z=0. Their overlaps are zero for the selected geometry. There is no defensible complete optical-path envelope or real hardware assembly; actual stage/telescope/optical interference remains **unverified**.

The bracket targets 5-axis billet CNC, but no CAM/holder/fixture collision simulation or machinist review was performed. Sharp re-entrant intersection/relief lines still need a manufacturable tool-radius/blend design review and re-analysis. **Not CNC-qualified or production-ready.** Temperature −40…85°C, MIL-STD-810G vibration, material traceability and actual joints/hardware are not qualified by this analysis.

## Requirement disposition

- **Passed in stated nominal model:** bracket mass, one connected solid, preserved nominal interfaces, supported modal target with point payload, independent loads/self-inertia, nominal yield ratios, force/moment balance, accepted mesh quality, frequency/displacement convergence, assumed hardware access/bearing and assumed stage/telescope clearances.
- **Failed:** literal/direct-coordinate cylinder clearance; X peak-stress convergence screen.
- **Unverified / conditional:** STEP coordinate registration, actual hardware and optical-path clearance, production tolerances, material/temperature allowables, real joint compliance, CNC tool/holder access and manufacturable blending, environmental/hardware qualification, globally optimal frequency. Full matrix with evidence: `results_final.json`.

## Complete iteration record

| Iteration | CAD mass g | Usable first mode Hz | Mesh screen passed? | Notes |
|---|---:|---:|---|---|
| 1 | 158.597 | invalid / unavailable | no | Failed C3D10 connectivity; no usable FEA. |
| 2 | 170.146 | invalid / unavailable | no | Original modal rejected (dependent MASS/MPC error); repaired static only. |
| 3 | 170.144 | 131.8787 | no | Valid modal/static; poor-element criterion failed. |
| 4 | 190.323 | 147.1514 | yes | Valid screening; conservative assumed stage envelope overlapped 5.859 mm³. |
| 5 | 190.323 | 146.9938 | no | Same CAD as 4; one poor element. |
| 6 | 190.323 | 146.9759 | yes | Same CAD as 4; local refinement passes; additional static convergence studies retained. |
| 7 | 189.363 | 143.4198 | no | Lower links moved rearward: assumed stage now clear; mesh-quality failed. |
| 8 | 189.532 | 143.4695 | yes | T3 root shifted 1 mm: valid final geometry, accepted mesh. Three invalid preflight implementations retained. |
| 9 | 189.532 | 143.2958 | yes | Same exact CAD as 8; refinement. |
| 10 | 189.532 | 143.0968 | yes | Same exact CAD as 8; finest accepted modal/static verification. |

Every folder iteration1…iteration10 contains DfM1, geometry1 and FEA1. Verification-only iterations are explicitly labeled rather than represented as new designs. Preflight geometry implementation failures, every exported attempt, meshes, solver decks, stdout/stderr, partial outputs and diagnostics remain in place. Iteration6's static-only 300s timeout retained X/Y outputs; Z was recovered in its own static-only job. Iteration10's first preparation was interrupted by a combined shell timeout; the complete preparation and sole modal invocation are in `model_complete`. These do not reset or bypass the modal counter.

Solver invocation ledger: `solver_invocations.jsonl`. Exactly ten modal invocations (two failed, eight completed) and the additional static-only diagnostics are preserved. No eleventh modal invocation is permitted. The user limit was not raised to the harness's larger operational cap.
