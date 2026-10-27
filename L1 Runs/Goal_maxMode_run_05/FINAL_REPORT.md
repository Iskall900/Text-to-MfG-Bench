# A15 — final best attempt after the 200 Hz continuation

## Outcome: 200 Hz requirement NOT met; modal budget exhausted
**Best retained iteration: 10.** CalculiX first supported mode = **126.6192 Hz**, versus the revised **200 Hz minimum**. The shortfall is **73.3808 Hz (36.69%)**. The first two computed modes (126.6192, 187.1182 Hz) are below 200 Hz. No full-compliance, hardware or CNC qualification is claimed.

Nominal bracket-only mass is **198.710 g**, below 200 g. Computed minimum independent-case yield FoS is **5.278** using assumed 240 MPa yield, but local peak stress is **not mesh-converged**, so this is not qualified strength evidence.

**10 geometry iterations and 10 modal attempts total; 0 remain.** Iterations 8–10 used exactly the three remaining modal calls. No counter reset, solver-path bypass, or further modal solve was used. The cylinder keep-out remains **waived by user**, not passed. The pre-200-Hz report, results, assumptions, ledger and manifest are preserved in `before_high_200hz/`; earlier initial-feasibility records and all prior iteration directories remain intact.

## Main files
- STEP CAD: `iteration10/geometry1/bracket.step`
- STL: `iteration10/geometry1/bracket.stl`
- Standalone Build123d source: `iteration10/geometry1/bracket_build123d.py`
- CAD views: `iteration10/geometry1/bracket_front.png`, `bracket_rear.png`
- Modal deck, frequencies, shapes: `iteration10/FEA1/modal.inp`, `modal.dat`, `modal.frd`
- First-mode image/animation: `iteration10/FEA1/first_mode_shape.png`, `first_mode_animation.gif`
- Coarse independent static inputs/results: `iteration10/FEA1/static_[X,Y,Z].inp/.dat/.frd/.log`
- Valid static refinement: `iteration10/FEA1/static_refined_straight_sided/`, with separate `case_X`, `case_Y`, `case_Z` job directories preserving solver scratch outputs
- DfM/access evidence: `iteration10/DfM1/`
- Final machine-readable outcome: `results_final.json`
- Updated accounting: `modal_run_ledger.json`; assumptions/criteria: `requirement_decisions.json`.

## Revision and design development
The user changed the first supported frequency requirement from 100 Hz to **200 Hz**, retaining ≤200 g mass, all exact interfaces and the original 10-iteration/10-modal-attempt total limits. Seven iterations/attempts had already been spent. The revised requirement is not evaluated against the obsolete 100 Hz threshold.

Iteration 8 replaced the flat-base load path with three spatial fan webs directly feeding round pads: 182.346 g and 116.6479 Hz refined. Iteration 9 used windowed skins, symmetric stiffener rims and stage returns: 191.936 g and 118.2930 Hz refined. Iteration 10 added a deeper open stage wedge and changed rear fan geometry to improve pitch resistance: 198.710 g and 126.6192 Hz on its valid coarse mesh. None attained 200 Hz. Iteration 10 is selected because it has the highest computed supported first frequency while retaining the mass/interface constraints; it is not claimed to be a global optimum.

Iteration 9's two window-fillet kernel construction failures are preserved in its geometry directory. No valid earlier iteration-9 bracket was exported or solved; the completed construction omitted a narrow window rather than retaining an unmachinably sharp/narrow aperture. These were CAD construction retries, not hidden additional modal calls.

## Final CAD and interface evidence
The final Build123d BRep is one valid connected solid. Seven STEP circular-edge centers match the A15 mounting coordinates within 1e-6 mm numerical tolerance in `interface_check.json`. The telescope datum stays at Z=0; the stage datum stays at Y=-7.164 mm. All seven clearance bores are 6.8 mm on the exact specified axes. A15.json defines three telescope fasteners and four stage fasteners; no fourth telescope mounting interface was fabricated.

Final nominal dimensions: pads R15.5 × 8 mm; rear skins 3.2 mm; solid front skin 3 mm; stiffener rim width 2.5 mm, projecting 4.5 mm each side; stage mounting panel 6 mm; triangular cheeks 3.2 mm; top rim 2.5 mm with 37 × 28 mm R4 through-opening. The stage wedge reaches Y=42 mm, primarily +Y of its mounting face. Rear windows have R3 corners. Attempted R0.8 pad-root blends failed and the actual CAD retains **sharp roots**; no successful root fillets are claimed. Bounding box is recorded in `geometry1/bounding_box.json`.

Mass derives from exact CAD volume 73596.4398 mm³ at 2700 kg/m³. The remaining nominal mass margin is only 1.290 g, not a validated tolerance/production allowance. Payload, hardware and reference envelopes are excluded from bracket-only mass and stiffness.

## CalculiX model
All ccx commands used `ccx` from PATH. Units mm, N, s, tonne. Assumed material: E=68,900 MPa, Poisson ratio 0.33, density=2700 kg/m³, yield=240 MPa. These are engineering assumptions, not certified allowables. No validated -40 to +85 C material curve or environmental qualification exists.

Grounded translational constraints are restricted to the three telescope bore surfaces (0≤Z≤8 mm); no pad/base faces or other solid regions are fixed. This is an ideal bonded-bore connection into a rigid telescope support, following the reference image. It does not verify actual preload, contact, friction, slip or support stiffness.

The payload is exactly 1.35 kg at (-1.6225,-57.164,125.21) mm, using the JSON Z coordinate, not the image's rounded 125.206. Non-rigid RBE3-style least-squares remote translation transfers through the four stage bores, with equal total weight per hole and 8 angular samples at each face. Only three equations connect the point-mass translation; bore nodes are not forced into a rigid stage plate. The CG MASS degrees of freedom are independent and three sampled bore components are equation pivots. The virtual-work mapping reproduces rigid translation/rotation and transfers offset moments. No physical connecting rods, payload stiffness or invented rotational inertia tensor is added. See `coupling_diagnostics.json` and `model.inc`.

Static X=10g, Y=3g, Z=3g cases are independently positive global axes. Payload CLOAD is at CG; bracket DLOAD GRAV uses the same signed acceleration on bracket elements only. Payload force is not duplicated in body loads. Under this fixed-boundary, no-contact, small-displacement linear elastic model, reversing an entire case reverses signed responses but preserves von Mises stress and displacement magnitude. This is not equivalence for a real frictional/unilateral joint.

## Supported modal result and failed refinement
Final modal job completed normally. Frequencies (Hz): 126.6192, 187.1182, 318.9408, 858.9745, 951.8988, 1413.7160, 1513.6780, 1952.5280. No zero/free rigid-body mode or imaginary frequency is reported. The first shape combines bending, pitch and torsion. `modal.frd` contains the actual shape; rendered amplitude is arbitrary, scaled to 15 mm maximum for visualization, not a service displacement.

The coarse curved C3D10 modal mesh has **29,025 bracket elements and 55,501 bracket nodes**, plus the payload MASS/reference and unused rotational bookkeeping node. Before the tenth invocation, the intended refined Gmsh high-order optimizer **aborted** with `Failed to reach critical value ... ScaledJac`. This happened before a combined refined modal deck was created. The already valid **single coarse modal deck** was then solved exactly once as attempt 10. There was **no refined modal solve and no modal repeat**. The final modal mesh-convergence requirement is therefore **unverified**, and the earlier coarse/fine comparisons for different geometries cannot establish it.

The complete failed optimizer log is `iteration10_convergence_mesh.log`. Subsequent static-only meshing disabled that optimizer but produced 7 inverted curved elements (minSJ=-7.1345); that mesh is retained in `static_refined_recovery` and was **rejected, never solved**. Static runner attempts at the absent original refined decks failed to read inputs; they are not modal attempts and their logs are retained.

A valid static-only recovery placed all C3D10 midside nodes at edge midpoints, retaining quadratic displacement interpolation and original CAD-classified bore node sets. It approximates curved CAD with planar facets. This mesh has **49,186 elements and 92,605 bracket nodes**, h=2.4 mm, no inverted elements, and CAD volume difference 0.0855%. Each independent static case was solved in a separate case directory. No additional FREQUENCY solve was made.

## Mesh-quality limits
Coarse min scaled Jacobian 0.10193, nonpositive count 0. Straight-sided static refinement min scaled Jacobian ≈1, nonpositive count 0. This meets the declared positivity/minSJ criterion, but **does not constitute full mesh adequacy**: minSJ≈1 for affine elements is not an aspect-ratio guarantee. Additional shape metrics show coarse min SICN 0.007178, with 12 elements below 0.05 (median 0.8221). The static recovery has min SICN 0.024450 and 3 below 0.05. Low-quality local slivers and sharp root/relief features remain concerns. Full diagnostics are in each `additional_mesh_quality.json`; warnings are preserved, not suppressed as proof of quality.

## Independent static evidence (valid straight-sided refinement)
Stress is maximum **unaveraged integration-point von Mises**, with no interface peak excluded to improve FoS. FoS=240 MPa/evaluated stress. Values are conditional on assumed material and ideal joints and are **not mesh-qualified local stresses**.

| Independent case | Raw peak stress (MPa) | Computed yield FoS | Max bracket displacement (mm) | Payload displacement magnitude (mm) |
|---|---:|---:|---:|---:|
| +X | 45.47 | 5.28 | 0.1789 | 0.1200 |
| +Y | 11.35 | 21.14 | 0.0567 | 0.0259 |
| +Z | 10.66 | 22.51 | 0.0334 | 0.0196 |

Nodal displacements, bore external RF values, integration-point stresses, reactions/resultants and moments about the global origin are retained in the `.dat`/`.frd` files and summary JSONs. Comparing bore RF resultants against payload plus CAD-mass/CG self-inertia gives maximum relative force residual 0.01333% and moment residual 0.01112%, below the selected 1% tolerance. CalculiX RF includes local applied body-load contributions at constrained nodes, so these are adopted-model external-force checks, not qualified physical bolt-contact forces.

Comparing coarse curved h3.5 against fine straight-sided h2.4 gives peak-stress changes X=14.57%, Y=42.03%, Z=24.68%. All exceed the selected 10% threshold; **local stress convergence is not established**. Different geometry approximations also prevent claiming a strict asymptotic convergence study. Payload displacement changes are X 0.42%, Y 0.45%, Z 0.27%; these are sensitivity data, not a replacement for stress/modal convergence.

## 5-axis manufacturing and access disposition
The design uses continuous fan/frame plates, open through-windows and a deep open wedge, not a complex cylindrical strut network or an intentionally enclosed cavity. However, 2.5 mm ribs, sharp unblended roots, acute connections and bolt-access relief terminations remain **DfM concerns**. Minimum-feature auditing, actual tool/holder reach, fixture planning, machining distortion, tolerances, CAM simulation and supplier approval are unverified. `FINAL_DFM_REVIEW.md` is a geometric assessment, not CNC qualification.

All seven interfaces pass separate **assumed** bolt-shank, washer, head, straight insertion and driver envelopes and full annular bearing checks. Assumptions: washer OD16/ID6.8/thickness1.5, head OD11/height6.5, driver OD11/100 mm reach, complete insertion sweep radius8/100 mm. Base screws approach +Z/travel -Z; stage screws approach +Y/travel -Y. Actual NAS1352/NAS620 details, length/engagement and tools remain unverified. Conservative stage/telescope half-box proxies do not overlap, but measured bodies and optical-path geometry are absent. The withdrawn cylinder is **waived**, not passed.

## Complete modal accounting
| Geometry / modal attempt | CAD mass (g) | First mode (Hz) | Modal status |
|---|---:|---:|---|
| 1 | 189.672 | 89.4674 | completed |
| 2 | 199.155 | 111.0035 | completed |
| 3 | 197.415 | 115.1052 | completed |
| 4 | 196.792 | No result | failed_input_duplicate_heading |
| 5 | 198.089 | No result | terminated_shell_timeout |
| 6 | 198.630 | 107.1327 | completed |
| 7 | 198.249 | 107.0815 | completed |
| 8 | 182.346 | 116.6479 | completed |
| 9 | 191.936 | 118.2930 | completed |
| 10 | 198.710 | 126.6192 | completed |

Exactly **10 modal invocations**, **8 completed and 2 earlier failed/terminated** (attempt 4 duplicate heading; attempt 5 shell timeout). Attempts 1–3 used superseded rigid stage-bore coupling; final designs use non-rigid transfer. Attempts 6–9 each have one FREQUENCY step with disconnected coarse/fine submodels; attempt 10 is one coarse model only. Each valid geometry iteration has one modal attempt. All folders remain `iterationN/geometry1`, `DfM1`, `FEA1`; no earlier iteration was deleted or moved into an archive.

## Passed / failed / unverified requirements
**Passed or conditionally demonstrated:** nominal mass; exact interfaces/planes; one connected valid solid; modeled offset payload and bracket self-inertia; constraints only on specified bores; generic assumed access/bearing envelopes; positive Jacobians in meshes actually solved; equilibrium residual criterion; 10-iteration/10-attempt total limits. Independent static FoS calculations exceed 1.4 but do not prove qualified strength because of material/joint and convergence limitations.

**Failed:** first supported mode ≥200 Hz (126.6192 Hz); selected local raw peak-stress convergence criterion; requested root-blend CAD construction. The obsolete 100 Hz requirement is not used to mark frequency as passing.

**Unverified:** final modal mesh convergence, local mesh adequacy/peak stress, actual material/temperature allowables, real hardware and engagement, real stage/telescope/optical clearance, physical joints/preload/friction/contact/stiffness, CNC feasibility/fixtures/CAM/distortion/tolerances, minimum feature thickness, environmental/MIL-STD-810G qualification and global optimum. **Waived:** cylindrical keep-out.

The budget is exhausted. Further geometry improvement or a refined modal validation would require explicit authorization beyond the original run limits; none was performed.
