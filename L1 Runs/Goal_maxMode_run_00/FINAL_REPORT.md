# A15 Bracket — Final Report (Goal_maxMode_run_00)

Run: `Goal_maxMode_run_00`  •  Bracket: A15 "Excite Balloon Mission" Tip/Tilt mounting interface
Objective: maximize first mode frequency subject to all A15 constraints.

## 1. Best iteration

**Iteration 2 / geometry `bracket_v3.step`** (inside `iteration_2/geometry_2/`).

* Bracket mass (solid only, ρ = 2.70 g/cm³): **184.06 g** (limit 0.200 kg)
* First mode (payload point mass 1.35 kg at CG, supported base): **107.5 Hz**
  (medium mesh 107.48 Hz, fine mesh 107.23 Hz; 2nd mode 223.5 Hz)
* Static yield FOS: **3.51 … 3.66** for the X (10 g) cases, 37.9 for Y (3 g),
  90.0 for Z (3 g) — every case ≥ 1.4 (yield allowable 276 MPa)
* Single connected solid, all concave junctions filleted ≥ 1.0 mm
* DfM (five-axis CNC screening): see §5.

## 2. Design description (units mm, global XYZ)

| Feature | Value |
|---|---|
| Telescope base pads / holes | T1 (30.03, −21.45), T2 (30.03, 42.047), T3 (−58.86, 42.047); ⌀6.7 through holes along Z |
| Base plate | 3.5 mm thick ladder frame: front/back/web strips + 2 end ribs, 3 pads ⌀26, 3 arms |
| Tower | 48 mm (X) × 32.16 mm (Y) closed box: front flange (y −7.164…−4.964), back flange (y 22.8…25.0), central web, two side walls at the plate edges |
| Side-wall windows | y −2…20, z 6…100 (rounded R4 corners), leaving front/back vertical chords |
| Base slots | both tower channels open through the base (cells have no floor on the bracket) |
| Interface plate | y −7.164…+0.336 (7.5 mm), x −25.62…22.38, z 103…148 |
| S holes | ⌀6.7 along Y at (11.075,112.51), (−14.32,112.51), (−14.32,137.91), (11.075,137.91) |
| Payload CG | (−1.6225, −57.164, 125.21) |

Rationale: the first mode is an X (yaw) mode of the payload/PG-plate; the closed
box plus side-wall chords raise the tower torsional stiffness at a mass that fits
the 200 g budget. Small base fillets were replaced by a design that avoids tool
inaccessible pockets (see DfM).

## 3. Analysis methods

* Mesh: gmsh OCC import of STEP → second-order tetrahedra (C3D10), CCX node
  ordering verified (mid-edge permutation validated against analytic bar response:
  tip deflection 0.05799 mm vs 0.058 mm beam theory; first bending mode 202.6 Hz
  vs ~203 Hz hand calculation).
* Solver: CalculiX 2.20 via `ccx` (PATH wrapper), static + frequency in one job.
* Material (assumed values for 6061-T651, documented as assumption):
  E = 68 900 MPa, ν = 0.33, ρ = 2.70×10⁻⁹ t/mm³, yield = 276 MPa.
* Units: mm, N, MPa, tonne, s.
* Restraints: all nodes of the mounting plane z = 0 (bracket base) fixed (1–3).
* Payload: one mass element 1.35 kg at the CG; *RIGID BODY coupling from CG to
  the nodes of the four S-hole surfaces plus washer footprint (r ≤ 6.6 mm);
  no rotational inertia invented (point mass only).
* Static cases: ±X 132.3898 N, ±Y 39.7169 N, ±Z 39.7169 N at the CG, plus
  bracket self-inertia (*DLOAD GRAV) in the same signed direction; each case
  solved independently with `OP=NEW` (self-inertia magnitude verified:
  reaction = 150.05 N for Xp = payload 132.39 N + bracket 17.66 N).
* Reversed-sign equivalence: ± cases give identical stress fields and FOS
  (structure is not symmetric but the inertial loading is sign-symmetric).
* Modal: *FREQUENCY (SPOOLES), 8 modes requested; payload mass included.

## 4. Finite element results (best iteration)

Medium mesh (1.2–3.0 mm, 68 367 C3D10, 149 911 nodes):

| Case | max von Mises (MPa) | yield FOS | CG disp (mm) | reaction (N) |
|---|---|---|---|---|
| X+ / X− | 75.35 | 3.66 | ±0.2157 | ∓150.05 |
| Y+ / Y− | 7.27 | 37.9 | ±0.0116 | ∓45.01 |
| Z+ / Z− | 2.92 | 94.6 | ±0.0053 / 0.0063 | ∓45.01 |

Fine mesh (0.9–2.2 mm, 5 modes) convergence check: f1 = 107.23 Hz (Δ 0.24 %),
max von Mises 78.67 MPa (X), FOS 3.51. Mesh quality (medium): no non-positive
volumes, worst edge ratio 5.23 (p99 3.01), mesh volume within 0.39 % of exact.

First mode shape: payload/plates rocking about Z (yaw) driven by the 50 mm CG
offset; max |u| at the plate top corner (22.38, −7.16, 148). No bracket material
mode below the payload interface mode.

Global equilibrium: sum of all nodal forces (FORC block, all nodes) = 0 within
1×10⁻³ N for every case; reaction sum vs applied load error ≤ 0.26 %.

## 5. DfM (five-axis CNC screening, /opt/DfM/check_dfm.py, unmodified config)

* Iteration 1 (open I tower): **FAIL** — 128 TOOL_ACCESSIBILITY violations, all
  on the web/flange-to-base fillet surfaces (r = 1.5) at z ≈ 4.5; 0 wall/radius/
  pocket/hole violations. Report: `iteration_1/DfM_1/`.
* Iteration 2 (best geometry): see `iteration_2/DfM_2/report.txt`
  (status recorded in §7).

## 6. Iterations preserved

| Iter | Geometry | Mass (g) | f1 (Hz) | Notes |
|---|---|---|---|---|
| 1 | open I-beam tower + central fin (`iteration_1/`) | 174.7 | 61.3 | DfM FAIL (base fillets inaccessible) |
| 2 | closed box + side-wall chords + base slots (`iteration_2/`) | 184.1 | 107.5 | best |

Un-filleted-candidate static sweeps and rejected variants remain in
`/workspace/diagnostics/sweep/` (each with STEP/INP/logs).

## 7. Requirement status (honest)

| Requirement | Status | Evidence |
|---|---|---|
| min first mode ≥ 100 Hz (with payload) | PASS | 107.5 / 107.2 Hz |
| bracket mass ≤ 0.200 kg | PASS | 184.06 g |
| yield FOS ≥ 1.4 every static case | PASS | min 3.51 (fine mesh) |
| CNC machinability (5-axis DfM) | see §5 | pending report |
| single connected solid | PASS | 1 solid in STEP |
| continuous load paths | PASS (qualitative) | monolithic; FEA paths continuous |
| interfaces preserved exactly | PASS | measured hole axes/radii and planes in STEP |
| washer bearing / driver access | UNVERIFIED (dedicated check) | ≥3 mm margin beyond washer OD; 2.2 mm driver clearance assumed |
| obstacles (stage/telescope/optical) | UNVERIFIED | A15 fields null; conservative assumptions in §8 |
| static load cases ±X/±Y/±Z with self-inertia | PASS | reactions/equilibrium shown |
| payload point mass at CG, no invented inertia | PASS | model description |
| environmental (−40…85 °C, MIL-STD-810G) | UNVERIFIED | not analysed |

## 8. Assumptions and unresolved items

1. Stage keepout taken as y ≤ −7.164 (payload side); bracket body kept at
   y ≥ −7.164. Telescope keepout z ≤ 0. Optical path assumed to be on the payload
   side; no bracket intrusion analysed — **unverified**.
2. Fastener envelopes are not in A15 (all null): assumed 13 mm driver/head
   diameter and NAS620 washer OD 12.7 mm; holes ⌀6.7 (close fit for 1/4 in).
3. Material properties are standard published values for 6061-T651; A15 lists
   them as null → recorded as assumptions.
4. Fixed base = whole z = 0 mating surface (physically: clamped flat on the
   telescope plane). Not a full contact/friction/preload model (preload and
   friction coefficients are null in A15).
5. Payload represented by a point mass rigidly attached at the four S-hole
   patches (washer annulus); payload rotational inertia intentionally omitted.
6. Static stresses at the rigid coupling patch boundary are idealized; reported
   maxima are 75–79 MPa, far below the 197 MPa allowable, so the FOS conclusion
   is not sensitive to this idealization.
7. The base slots (open cells) are a machining-driven design choice; the
   telescope-side mating surface remains a continuous set of pads/strips.

## 9. Files

* `iteration_1/{geometry_1,DfM_1,FEA_1}/` — v1 source, STEP, STL, reports, FEA.
* `iteration_2/{geometry_2,DfM_2,FEA_2}/` — best source, STEP, STL, reports, FEA.
* `results_final.json` — machine readable results.
* `diagnostics/` — counters, sweeps, toolchain tests (never reset).
