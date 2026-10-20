"""Mesh the bracket STEP with gmsh -> CalculiX mesh.inp (C3D10).

Writes:
  mesh.inp        nodes + C3D10 elements
  mesh_meta.json  counts, node sets (holes / cg), bbox
"""
from __future__ import annotations

import json
import math
import os
import sys

import gmsh
import numpy as np

T_HOLES = {
    "T1": (30.03, -21.45),
    "T2": (30.03, 42.047),
    "T3": (-58.86, 42.047),
}
S_HOLES = {
    "S1": (11.075, 112.51),
    "S2": (-14.32, 112.51),
    "S3": (-14.32, 137.91),
    "S4": (11.075, 137.91),
}
STAGE_PLANE_Y = -7.164
PAYLOAD_CG = (-1.6225, -57.164, 125.21)
HOLE_R = 3.45  # clearance hole radius (6.9 dia)


def main():
    step = sys.argv[1]
    outdir = sys.argv[2]
    max_size = float(sys.argv[3]) if len(sys.argv) > 3 else 2.8
    min_size = float(sys.argv[4]) if len(sys.argv) > 4 else 0.8
    ho_opt = int(sys.argv[5]) if len(sys.argv) > 5 else 2
    alg3d = int(sys.argv[6]) if len(sys.argv) > 6 else 10
    os.makedirs(outdir, exist_ok=True)

    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.occ.importShapes(step)
    gmsh.model.occ.synchronize()
    vols = gmsh.model.getEntities(3)
    assert len(vols) == 1, f"expected 1 volume, got {len(vols)}"

    gmsh.option.setNumber("Mesh.MeshSizeMax", max_size)
    gmsh.option.setNumber("Mesh.MeshSizeMin", min_size)
    gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 1)
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 14)
    gmsh.option.setNumber("Mesh.Algorithm3D", alg3d)
    gmsh.option.setNumber("Mesh.ElementOrder", 2)
    gmsh.option.setNumber("Mesh.SecondOrderLinear", 0)
    gmsh.option.setNumber("Mesh.HighOrderOptimize", ho_opt)
    gmsh.model.mesh.generate(3)

    # ---- extract nodes ----
    node_tags, coords, _ = gmsh.model.mesh.getNodes()
    coords = np.array(coords, float).reshape(-1, 3)
    tag_to_idx = {int(t): i for i, t in enumerate(node_tags)}

    # ---- extract only 3D elements (10-node tets = gmsh type 11) ----
    elem_blocks = []
    conns = []
    for etype, etags, ntags in zip(*gmsh.model.mesh.getElements(3)):
        if etype == 11:
            elem_blocks.append(np.array(etags, int))
            n = len(ntags) // len(etags)
            conns.append(np.array(ntags, int).reshape(-1, n))
    if not conns:
        raise RuntimeError("no C3D10 elements produced")
    conn = np.vstack(conns)
    # gmsh Tet10 order [0..7,8,9] -> Abaqus/CalculiX C3D10 [0..7,9,8]
    conn = conn[:, [0, 1, 2, 3, 4, 5, 6, 7, 9, 8]]
    etags = np.concatenate(elem_blocks)
    # renumber element ids 1..N in order
    order = np.argsort(etags)
    conn = conn[order]

    # ---- signed corner-tet volumes (mesh sanity) ----
    p0 = coords[conn[:, 0]]
    p1 = coords[conn[:, 1]]
    p2 = coords[conn[:, 2]]
    p3 = coords[conn[:, 3]]
    jac = np.einsum("ij,ij->i", np.cross(p1 - p0, p2 - p0), p3 - p0) / 6.0
    n_neg = int((jac <= 0).sum())
    print(f"corner-tet volumes: min={jac.min():.4g} n_nonpositive={n_neg}")

    # ---- node sets by coordinates ----
    def ring_nodes(axis, c1, c2, r_in, r_out, a_lo, a_hi):
        if axis == "z":
            rr = np.hypot(coords[:, 0] - c1, coords[:, 1] - c2)
            aa = coords[:, 2]
        elif axis == "y":
            rr = np.hypot(coords[:, 0] - c1, coords[:, 2] - c2)
            aa = coords[:, 1]
        else:
            raise ValueError(axis)
        m = (rr >= r_in) & (rr <= r_out) & (aa >= a_lo) & (aa <= a_hi)
        return np.where(m)[0]

    base_top = 4.0  # informational only
    sets = {}
    for name, (tx, ty) in T_HOLES.items():
        sets[name] = ring_nodes("z", tx, ty, HOLE_R - 0.25, HOLE_R + 0.25,
                                -0.5, 30.0)
    for name, (sx, sz) in S_HOLES.items():
        sets[name] = ring_nodes("y", sx, sz, HOLE_R - 0.25, HOLE_R + 0.25,
                                STAGE_PLANE_Y - 0.5, 30.0)

    fix = sorted(set(np.concatenate([sets[t] for t in T_HOLES]).tolist()))
    sall = sorted(set(np.concatenate([sets[s] for s in S_HOLES]).tolist()))

    # ---- write inp ----
    with open(os.path.join(outdir, "mesh.inp"), "w") as f:
        f.write("*HEADING\nA15 bracket mesh\n")
        f.write("*NODE\n")
        for i, (x, y, z) in enumerate(coords, start=1):
            f.write(f"{i}, {x:.6f}, {y:.6f}, {z:.6f}\n")
        # include the payload CG node (id len+1)
        f.write(f"{len(coords)+1}, {PAYLOAD_CG[0]:.6f}, {PAYLOAD_CG[1]:.6f},"
                f" {PAYLOAD_CG[2]:.6f}\n")
        f.write("*ELEMENT, TYPE=C3D10, ELSET=EALL\n")
        for i, row in enumerate(conn, start=1):
            f.write(f"{i}, " + ", ".join(str(tag_to_idx[int(t)] + 1) for t in row)
                    + "\n")
        # node sets (node numbering used in this file = tag_to_idx+1)
        def write_nset(name, idxs):
            f.write(f"*NSET, NSET={name}\n")
            for k in range(0, len(idxs), 16):
                f.write(", ".join(str(i + 1) for i in idxs[k:k + 16]) + "\n")
        for name in T_HOLES:
            write_nset(name, sets[name])
        for name in S_HOLES:
            write_nset(name, sets[name])
        write_nset("FIX", np.array(fix, int))
        write_nset("SALL", np.array(sall, int))
        f.write(f"*NSET, NSET=CG\n{len(coords)+1}\n")

    meta = {
        "n_nodes": len(coords) + 1,
        "n_elem": len(conn),
        "hole_nodes": {k: len(v) for k, v in sets.items()},
        "n_fix": len(fix),
        "n_sall": len(sall),
        "cg_node": len(coords) + 1,
        "bbox_min": coords.min(0).tolist(),
        "bbox_max": coords.max(0).tolist(),
        "max_size": max_size,
        "min_size": min_size,
        "min_corner_vol": float(jac.min()),
        "n_nonpositive": n_neg,
    }
    with open(os.path.join(outdir, "mesh_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    gmsh.finalize()
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
