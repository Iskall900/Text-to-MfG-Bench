Using Build123d, design a bracket that meets all requirements in A15.json. 

Constraints:
For FEA, use CalculiX. You are limited to 15 total modal FEA runs. Each geometry iteration gets at least one.
Spend one extra modal run on a refined mesh of your final design to show the first mode frequency changes by less than 2%. That run counts toward the 15.
If you hit your modal FEA limit, respond with your best attempt. 
Web search is allowed, however you are unable to download anything. Build123d and CalculiX docs are already cached in your project. 
Do not attempt to run topology optimizaton.


FEA instructions - "FEA_refrence.png" is a visual summary of FEA requirements. 
Rigid constraints are only applied to bolt holes. 
Model the 1.35 kg payload as a point mass at its center of gravity (TopLoad), connected rigidly to the S1–S4 hole surfaces. Use this payload model for both static and modal analyses.
Static strength: maximum von Mises stress in the bracket must not exceed 276 MPa / 1.4 = 197 MPa in every load case.
Ignore the temperature range and the MIL-STD-810G vibration profile; only the first-mode frequency requirement and the static load cases apply.


Manufacturing:
Manufacturing target is 5-axis CNC machining from a single 6061-T651 aluminum billet (per A15.json).
The bracket will be checked for manufacturability after you finish, against the limits below.
Treat these limits as hard requirements, the same as the FEA requirements.

Design approach:
- Build the bracket from flat plates, ribs, and webs of constant thickness. Remove mass with open
  pockets and through-windows, not with trusses or lattices.
- Do not use round struts, tube networks, or lattice structures.
- Every surface must be reachable by a cutting tool approaching from one of these directions:
  +Z, -Z, +Y, -Y, or the normal of a flat face on the bracket. Ribs should run parallel to one
  of these directions so a tool can reach their sides.
- Design for at most 4 machine setups.

Limits (all dimensions in mm):
| Feature                        | Limit                                                    |
|--------------------------------|----------------------------------------------------------|
| Wall, rib, web thickness       | >= 3.0                                                   |
| Unsupported rib height         | <= 8 x rib thickness                                     |
| Internal corner radius         | >= 3.0 (vertical corners of pockets and windows)         |
| Pocket floor-to-wall radius    | >= 1.0, or a sharp corner                                |
| Pocket depth                   | <= 4 x pocket width (narrowest opening); always <= 40    |
| Slot width                     | >= 6.0                                                   |
| Bolt holes (1/4 in fasteners)  | 6.731 (0.265 in) diameter through-holes, per the A15 STEP |
| Hole depth                     | <= 6 x hole diameter                                     |
| Boss or standoff height        | <= 2 x its diameter                                      |
| Closed internal cavities       | none                                                     |
| Undercuts                      | none, except where a standard T-slot or dovetail cutter  |
|                                | can reach from an allowed direction                      |

Fastener access: leave a clear straight path along each bolt axis for the bolt, washer, head,
and a driver. Leave flat, perpendicular seating under each washer, at least 16 mm in diameter.

Modeling rules:
- Put corner radii into 2D sketches before extruding or cutting. Do not rely on 3D fillets
  added afterward.
- If a fillet operation fails, change the geometry until it succeeds. A sharp internal corner
  that remains in the final CAD counts as a failure.
- Before submitting, measure from the final CAD: minimum wall thickness, minimum internal
  corner radius, maximum pocket depth-to-width ratio, and maximum hole depth-to-diameter
  ratio. Record these four values in final/results.json.

Do not produce CAM plans, NC code, setup sheets, or qualification disclaimers.


Orginization: Format - For every geometry iteration, create a new numbered folder: iteration1, iteration2, iteration3, and so on. Inside each iteration folder, create two folders: one called “geometry” and a “FEA” folder. 
Create a new iteration folder for every design change. 
Maximum number of iterations is 14, so the 15 modal runs cover one run per iteration plus the final convergence run.

Keep out zone:
The keep-out zone is a cylinder, 100 mm in diameter and 109.2 mm long, with its axis parallel to global Y. Its circular face lies in the S1–S4 mounting plane at Y = −7.164 mm, centered at X = −1.6225 mm, Z = 125.21 mm (the center of the four-bolt pattern). It extends toward negative Y, spanning Y = −116.364 to −7.164 mm. The bracket's flat S1–S4 mounting face, which seats against the stage in the plane Y = −7.164, may touch the zone's circular face. Every other bracket surface must stay at least 2.0 mm clear of this keep out zone, and no part of the bracket may enter it.



Final deliverables:
Create a folder named "final" containing exactly these two files:
- bracket.step: the final bracket geometry, as one solid.
- results.json, exactly this structure (same keys, same order, no extra keys):

```json
{
  "iteration": "iteration7",
  "bracket_mass_kg": 0.000,
  "first_mode_frequency_hz": 0.0,
  "max_von_mises_stress_MPa": { "X": 0.0, "Y": 0.0, "Z": 0.0 },
  "min_keepout_clearance_mm": 0.00,
  "min_wall_thickness_mm": 0.00,
  "min_internal_corner_radius_mm": 0.00,
  "max_pocket_depth_to_width_ratio": 0.00,
  "max_hole_depth_to_diameter_ratio": 0.00,
  "assumptions": ["short sentence", "short sentence"]
}
```

  Rules:
  - "iteration" is a string that exactly matches an existing iteration folder name.
  - Every other value except "assumptions" is a plain JSON number in the unit named
    in its key. No strings, units, ranges, nulls, or nested objects, except the
    stress object, which has exactly the keys "X", "Y", "Z".
  - "min_keepout_clearance_mm" is the smallest distance from the bracket to the keep-out
    zone, excluding the S1–S4 mounting face; it is positive when the bracket is clear of the zone and must be at least 2.0.
  - A design with no pockets reports 0 for "max_pocket_depth_to_width_ratio". A design
    with no holes reports 0 for "max_hole_depth_to_diameter_ratio".
  - "assumptions" is an array of strings, one assumption per string. Use [] if there are none.

Requirements cannot be waived, relaxed, or reinterpreted. No one is available to answer questions. Where a value is unspecified, choose the conservative option and state the assumption.

Do not respond until you have a bracket that meets all requirements. 



