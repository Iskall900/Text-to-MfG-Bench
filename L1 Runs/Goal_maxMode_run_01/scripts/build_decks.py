"""Build CalculiX input decks (modal + 6 static cases) from mesh.inp.

Units: mm, N, MPa, tonne, s.  Aluminium 6061-T651.
  E = 69000 MPa, nu = 0.33, rho = 2.70e-9 tonne/mm^3, yield = 276 MPa.

Fixed (rigid) boundary at the three base bolt bores (T1..T3).
Payload: 1.35 kg point mass at the CG, attached to the four S-bore surfaces
with a rigid remote connection (bolt-hole interface).
"""
from __future__ import annotations

import json
import os
import sys

E = 69000.0
NU = 0.33
RHO = 2.70e-9        # tonne/mm^3
YIELD = 276.0        # MPa (6061-T651)
PAYLOAD_MASS = 1.35e-3   # tonne
G = 9806.65          # mm/s^2

CASES = {
    "X": ("x", 132.389775),
    "Y": ("y", 39.7169325),
    "Z": ("z", 39.7169325),
}


def main():
    feadir = sys.argv[1]
    mesh = os.path.join(feadir, "mesh.inp")
    meta = json.load(open(os.path.join(feadir, "mesh_meta.json")))
    cg = meta["cg_node"]
    with open(mesh) as f:
        mesh_txt = f.read()

    mass_eid = meta["n_elem"] + 1
    core = f"""*ELEMENT, TYPE=MASS, ELSET=MASSEL
{mass_eid}, {cg}
*MASS, ELSET=MASSEL
{PAYLOAD_MASS:.6e}
*RIGID BODY, NSET=SALL, REF NODE={cg}
*SOLID SECTION, ELSET=EALL, MATERIAL=AL6061
*MATERIAL, NAME=AL6061
*ELASTIC
{E}, {NU}
*DENSITY
{RHO:.6e}
*BOUNDARY
FIX, 1, 3, 0.
"""

    # ---------------- modal ----------------
    modal = mesh_txt + core + """*STEP
*FREQUENCY
10
*NODE FILE
U
*EL FILE
S
*END STEP
"""
    with open(os.path.join(feadir, "modal.inp"), "w") as f:
        f.write(modal)

    # ---------------- static cases ----------------
    for case, (axis, mag) in CASES.items():
        for s, sg in (("p", 1.0), ("n", -1.0)):
            dof = {"x": 1, "y": 2, "z": 3}[axis]
            d = {"x": "1., 0., 0.", "y": "0., 1., 0.",
                 "z": "0., 0., 1."}[axis]
            if sg < 0:
                d = "-1., 0., 0." if axis == "x" else \
                    ("0., -1., 0." if axis == "y" else "0., 0., -1.")
            step = f"""*STEP
*STATIC
*CLOAD
CG, {dof}, {sg * mag:.8g}
*DLOAD
EALL, GRAV, {G:.5f}, {d}
*NODE PRINT, NSET=FIX, TOTALS=YES
RF
*NODE PRINT, NSET=CG
U
*NODE FILE
U, RF
*EL FILE
S
*END STEP
"""
            with open(os.path.join(feadir, f"static_{case}{s}.inp"), "w") as f:
                f.write(mesh_txt + core + step)
    print("decks written to", feadir)


if __name__ == "__main__":
    main()
