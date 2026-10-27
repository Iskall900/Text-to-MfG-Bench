# A15 iteration9: FEA evidence

Wall raised to 3.5 mm to use available mass for stiffness; 2.7 mm mesh. Highest first frequency among completed, single-solid, mass-feasible runs. Selected best completed candidate.

CalculiX 2.20 via PATH `ccx`. Units N, mm, s, tonne. C3D10 bracket elements; E=68900 MPa, nu=0.33, density=2700 kg/m³. Yield screening allowable 240 MPa (engineering assumption, not temperature-qualified or material-certified).

Constraints: zero translations only on T1/T2/T3 bore surfaces; no fixed pad faces. Stage holes remain deformable. 112 well-spread bore nodes form a least-squares distributed remote connection reproducing rigid translation/rotation fields. Exactly 1.35 kg point mass at (-1.6225,-57.164,125.21) mm; no invented rotational inertia. In iteration1 the failed first input used a dependent MASS node; the static diagnostic and all later iterations keep that node independent.

Independent +X 10g, +Y 3g, +Z 3g cases include payload offset moments and same-signed bracket self inertia. Full case sign reversal is equivalent for von Mises in this linear, unpreloaded idealization. Actual preload/contact/friction/stiffness are unknown.

| Case | Maximum unaveraged Gauss von Mises MPa | Yield FoS (240 MPa) | Maximum bracket displacement mm |
|---|---:|---:|---:|
| X | 36.991 | 6.488 | 0.036884 |
| Y | 14.643 | 16.390 | 0.018625 |
| Z | 9.148 | 26.235 | 0.016799 |

First modal frequency: 171.1534 Hz. See input decks, `.dat` (integration-point stresses, displacements, reactions, spectrum), `.frd` (field data), mesh `.msh`, `mesh_and_model.json`, `mesh_data.npz`, and result JSON. All peaks include supports and notch regions; no favorable exclusions or nodal averaging. Mesh convergence and comparison are recorded in `/workspace/convergence.json`. Geometry/interface and environmental limitations prevent hardware qualification.
