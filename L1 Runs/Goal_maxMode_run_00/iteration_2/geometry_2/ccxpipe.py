"""Pipeline: Build123d STEP -> gmsh tet10 mesh -> CalculiX .inp -> run ccx -> parse FRD.

Units throughout: mm, N, MPa, tonne, s  (density in tonne/mm^3).
"""
from __future__ import annotations

import os
import re
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np

# gmsh tetra10 node order: [v0,v1,v2,v3, e01,e12,e20,e03,e23,e13]
# CalculiX/Abaqus C3D10 order: [v0,v1,v2,v3, e01,e12,e20,e03,e13,e23]
GMSH_TO_CCX_TET10 = [0, 1, 2, 3, 4, 5, 6, 7, 9, 8]


def mesh_step(step_path, size_min, size_max, curvature=None, dist_min=None,
              optimize=True, quiet=True):
    """Mesh a STEP file with gmsh and return (nodes Nx3 float64, tets Mx10 int32)."""
    import gmsh

    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0 if quiet else 1)
        gmsh.option.setNumber("General.Verbosity", 1 if quiet else 3)
        gmsh.model.add("part")
        gmsh.model.occ.importShapes(str(step_path))
        gmsh.model.occ.synchronize()
        if curvature is not None:
            gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", curvature)
        if dist_min is not None:
            gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 1)
        gmsh.option.setNumber("Mesh.MeshSizeMin", size_min)
        gmsh.option.setNumber("Mesh.MeshSizeMax", size_max)
        gmsh.option.setNumber("Mesh.ElementOrder", 1)
        gmsh.option.setNumber("Mesh.Algorithm3D", 1)  # Delaunay
        gmsh.option.setNumber("Mesh.Optimize", 1 if optimize else 0)
        gmsh.option.setNumber("Mesh.OptimizeNetgen", 1 if optimize else 0)
        gmsh.model.mesh.generate(3)
        if optimize:
            gmsh.model.mesh.optimize("Netgen")
        gmsh.model.mesh.setOrder(2)
        ntags, ncoords, _ = gmsh.model.mesh.getNodes()
        nodes = np.asarray(ncoords, dtype=np.float64).reshape(-1, 3)
        tag2idx = {int(t): i for i, t in enumerate(ntags)}
        etypes, etags, enodes = gmsh.model.mesh.getElements(3)
        tets = []
        for et, en in zip(etypes, enodes):
            if et != 11:
                raise RuntimeError(f"unexpected element type {et}")
            arr = np.asarray(en, dtype=np.int64).reshape(-1, 10)
            remap = np.array([tag2idx[int(t)] for t in arr.ravel()]).reshape(-1, 10)
            tets.append(remap[:, GMSH_TO_CCX_TET10])
        tets = np.vstack(tets) + 1  # 1-based connectivity
        return nodes, tets
    finally:
        gmsh.finalize()


def nset_from_coords(nodes, mask):
    return np.nonzero(mask)[0] + 1  # 1-based node ids


def write_inp(path, nodes, tets, sets, cg_coord, mass_kg, mat=None,
              steps=("freq", "static"), n_modes=10, jobname="job"):
    """Write a CalculiX input file.

    sets: dict name -> 1-based node id array.
    steps: sequence containing 'freq' and/or 'static'; each static case is
           (name, fx, fy, fz) applied at CG, plus gravity in same direction.
    """
    if mat is None:
        mat = dict(name="AL6061T651", E=68900.0, nu=0.33, rho=2.7e-9, yield_MPa=276.0)
    g = 9806.65  # mm/s^2 per 1 g
    cg_id = len(nodes) + 1
    has_cg = cg_coord is not None
    lines = []
    lines.append("*HEADING")
    lines.append(f" job {jobname}")
    lines.append("*NODE")
    for i, (x, y, z) in enumerate(nodes, 1):
        lines.append(f"{i}, {x:.9g}, {y:.9g}, {z:.9g}")
    if has_cg:
        lines.append(f"{cg_id}, {cg_coord[0]:.9g}, {cg_coord[1]:.9g}, {cg_coord[2]:.9g}")
    lines.append("*ELEMENT, TYPE=C3D10, ELSET=EALL")
    for i, row in enumerate(tets, 1):
        lines.append(f"{i}, " + ", ".join(str(int(n)) for n in row))
    for name, ids in sets.items():
        lines.append(f"*NSET, NSET={name}")
        ids = np.asarray(ids, dtype=np.int64)
        for j in range(0, len(ids), 16):
            chunk = ids[j:j + 16]
            suffix = "," if j + 16 < len(ids) else ""
            lines.append(", ".join(str(int(v)) for v in chunk) + suffix)
    if cg_coord is not None and mass_kg:
        lines.append(f"*NSET, NSET=CGNODE")
        lines.append(str(cg_id))
        lines.append("*ELEMENT, TYPE=MASS, ELSET=PAYLOAD")
        lines.append(f"{len(tets) + 1}, {cg_id}")
        lines.append("*MASS, ELSET=PAYLOAD")
        lines.append(f"{mass_kg*1e-3:.9g}")
        if 'PATCH' in sets:
            lines.append(f"*RIGID BODY, NSET=PATCH, REF NODE={cg_id}")
    lines.append(f"*MATERIAL, NAME={mat['name']}")
    lines.append("*ELASTIC")
    lines.append(f"{mat['E']:.9g}, {mat['nu']:.9g}")
    lines.append("*DENSITY")
    lines.append(f"{mat['rho']:.9g}")
    lines.append("*SOLID SECTION, ELSET=EALL, MATERIAL=" + mat["name"])
    lines.append("*BOUNDARY")
    lines.append("FIX, 1, 3")
    for st in steps:
        if st[0] == "freq":
            lines.append("*STEP")
            lines.append("*FREQUENCY, SOLVER=SPOOLES")
            lines.append(str(st[1] if len(st) > 1 else n_modes))
            lines.append("*NODE FILE")
            lines.append("U")
            lines.append("*END STEP")
        elif st[0] == "static":
            _, name, fx, fy, fz = st
            lines.append("*STEP")
            lines.append("*STATIC")
            lines.append("*CLOAD")
            lines.append(f"CGNODE, 1, {fx:.9g}")
            lines.append(f"CGNODE, 2, {fy:.9g}")
            lines.append(f"CGNODE, 3, {fz:.9g}")
            nrm = np.sqrt(fx * fx + fy * fy + fz * fz)
            mag = nrm / mass_kg  # mm/s2
            ux, uy, uz = fx / nrm, fy / nrm, fz / nrm
            lines.append("*DLOAD")
            lines.append("EALL, GRAV, %.9g, %.9g, %.9g, %.9g" % (mag, ux, uy, uz))
            lines.append("*EL FILE")
            lines.append("S")
            lines.append("*NODE FILE")
            lines.append("U, RF")
            lines.append("*NODE PRINT, NSET=CGNODE")
            lines.append("U, RF")
            lines.append("*END STEP")
    Path(path).write_text("\n".join(lines) + "\n")
    return cg_id


def run_ccx(inp_path, cwd=None, timeout=7200):
    """Run ccx on the input file (basename, no extension). Returns (rc, stdout, stderr)."""
    cwd = Path(cwd or Path(inp_path).parent)
    job = Path(inp_path).stem
    p = subprocess.run(["ccx", job], cwd=str(cwd), capture_output=True, text=True,
                       timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def parse_frd(path):
    """Parse a CalculiX .frd file.

    Returns {"nodes": {nid: [x,y,z]},
             "blocks": [ {"name":str, "step":int, "data":{nid: np.array}} ...]}
    """
    lines = Path(path).read_text(errors="replace").splitlines()
    nodes = {}
    blocks = []
    in_block = False
    cur = None
    pstep = 0
    for ln in lines:
        if ln.startswith("    1PSTEP"):
            toks = ln.split()
            try:
                pstep = int(toks[1])
            except Exception:
                pass
            continue
        if ln.startswith(" -4"):
            toks = ln[3:].split()
            name = toks[0] if toks else "?"
            cur = {"name": name, "step": pstep, "data": {}}
            blocks.append(cur)
            in_block = True
            continue
        if ln.startswith(" -3"):
            in_block = False
            cur = None
            continue
        if ln.startswith(" -1"):
            if in_block and cur is not None:
                try:
                    nid = int(ln[3:13])
                except ValueError:
                    continue
                vals = []
                for k in range(13, len(ln), 12):
                    chunk = ln[k:k + 12]
                    if chunk.strip():
                        vals.append(float(chunk))
                cur["data"][nid] = np.array(vals)
            else:
                try:
                    nid = int(ln[3:13])
                    vals = []
                    for k in range(13, len(ln), 12):
                        chunk = ln[k:k + 12]
                        if chunk.strip():
                            vals.append(float(chunk))
                    if len(vals) >= 3 and nid not in nodes:
                        nodes[nid] = vals[:3]
                except ValueError:
                    pass
            continue
    return {"nodes": nodes, "blocks": blocks}


def modal_disp_blocks(frd_data, n_modes):
    """Return list of DISP blocks that belong to the *FREQUENCY step (first n_modes)."""
    out = []
    for b in frd_data["blocks"]:
        if b["name"].upper() in ("DISP", "U"):
            out.append(b)
        if len(out) == n_modes:
            break
    return out


def static_blocks(frd_data, n_modes, case_index):
    """Return (disp, stress, forc) blocks for the case_index-th static case."""
    disp, stress, forc = [], [], []
    seen_disp = 0
    for b in frd_data["blocks"]:
        n = b["name"].upper()
        if n in ("DISP", "U"):
            seen_disp += 1
            if seen_disp > n_modes:
                disp.append(b)
        elif n in ("STRESS", "S"):
            stress.append(b)
        elif n in ("FORC", "RF"):
            forc.append(b)
    get = lambda lst: lst[case_index] if case_index < len(lst) else None
    return get(disp), get(stress), get(forc)


def max_von_mises(block):
    """Max von Mises over a stress block. Returns (vm, nid, count)."""
    best = -1.0
    best_node = None
    count = 0
    data = block["data"] if block else {}
    for nid, v in data.items():
        if len(v) < 6:
            continue
        count += 1
        sxx, syy, szz, sxy, syz, szx = v[:6]
        vm = np.sqrt(0.5 * ((sxx - syy) ** 2 + (syy - szz) ** 2 +
                            (szz - sxx) ** 2) + 3 * (sxy ** 2 + syz ** 2 + szx ** 2))
        if vm > best:
            best, best_node = float(vm), nid
    return best, best_node, count


def parse_dat_frequencies(path):
    """Extract eigenfrequencies (cycles/time) from CalculiX .dat."""
    txt = Path(path).read_text(errors="replace")
    freqs = []
    in_table = False
    for ln in txt.splitlines():
        if "E I G E N V A L U E" in ln and "O U T P U T" in ln:
            in_table = True
            continue
        if in_table:
            toks = ln.split()
            if len(toks) >= 3 and toks[0].isdigit():
                try:
                    freqs.append(float(toks[3]))
                except ValueError:
                    pass
            elif ln.strip() == "":
                if freqs:
                    break
    return freqs
