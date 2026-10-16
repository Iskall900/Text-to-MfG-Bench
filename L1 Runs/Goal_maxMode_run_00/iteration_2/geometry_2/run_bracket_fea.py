#!/usr/bin/env python3
"""Run static + modal CalculiX analysis of the A15 bracket.

Usage: run_bracket_fea.py STEP OUTDIR [--smin 0.8] [--smax 2.2] [--curv 10]
                                    [--modes 8] [--job job] [--timeout 7200]

Writes job.inp, job.log, job.dat, job.frd and summary.json in OUTDIR.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ccxpipe as cp

# A15 constants
PLANE_Y = -7.164
T_HOLES = [(30.03, -21.45), (30.03, 42.047), (-58.86, 42.047)]
S_HOLES = [(11.075, 112.51), (-14.32, 112.51), (-14.32, 137.91), (11.075, 137.91)]
CG = (-1.6225, -57.164, 125.21)
PAYLOAD_KG = 1.35
G = 9.80665
CASES = [
    ("Xp", 10.0 * G * PAYLOAD_KG, 0.0, 0.0),
    ("Xn", -10.0 * G * PAYLOAD_KG, 0.0, 0.0),
    ("Yp", 0.0, 3.0 * G * PAYLOAD_KG, 0.0),
    ("Yn", 0.0, -3.0 * G * PAYLOAD_KG, 0.0),
    ("Zp", 0.0, 0.0, 3.0 * G * PAYLOAD_KG),
    ("Zn", 0.0, 0.0, -3.0 * G * PAYLOAD_KG),
]
YIELD_MPa = 276.0
DENSITY_T_MM3 = 2.7e-9


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step")
    ap.add_argument("outdir")
    ap.add_argument("--smin", type=float, default=0.8)
    ap.add_argument("--smax", type=float, default=2.2)
    ap.add_argument("--curv", type=float, default=10.0)
    ap.add_argument("--modes", type=int, default=8)
    ap.add_argument("--job", default="job")
    ap.add_argument("--timeout", type=float, default=7200.0)
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    from build123d import import_step
    bracket_mass_kg = import_step(args.step).volume * DENSITY_T_MM3 * 1e3
    t0 = time.time()
    nodes, tets = cp.mesh_step(args.step, args.smin, args.smax, curvature=args.curv)
    nmesh = time.time() - t0
    fix = cp.nset_from_coords(nodes, nodes[:, 2] < 0.05)
    # patch: nodes on/near the four S hole surfaces
    patch_mask = np.zeros(len(nodes), dtype=bool)
    for (xs, zs) in S_HOLES:
        r = np.sqrt((nodes[:, 0] - xs) ** 2 + (nodes[:, 2] - zs) ** 2)
        patch_mask |= (r < 4.6) & (nodes[:, 1] > -7.4) & (nodes[:, 1] < 0.6)
    patch = cp.nset_from_coords(nodes, patch_mask)
    steps = [("freq", args.modes)]
    for name, fx, fy, fz in CASES:
        steps.append(("static", name, fx, fy, fz))
    steps_static = len(CASES)
    inp = outdir / f"{args.job}.inp"
    cp.write_inp(inp, nodes, tets, {"FIX": fix, "PATCH": patch}, CG, PAYLOAD_KG,
                 steps=steps, jobname=args.job)
    # geometry mass from the inp volume (computed by ccx? use file size) - computed in summary externally
    t1 = time.time()
    rc, out, err = cp.run_ccx(inp, cwd=outdir, timeout=args.timeout)
    (outdir / f"{args.job}.ccx.log").write_text(out + "\n" + err)
    solve_time = time.time() - t1
    freqs = cp.parse_dat_frequencies(outdir / f"{args.job}.dat")
    frd = cp.parse_frd(outdir / f"{args.job}.frd")
    dat_txt = (outdir / f"{args.job}.dat").read_text(errors="replace")
    result = {
        "step": str(args.step),
        "bracket_mass_kg": bracket_mass_kg,
        "bracket_volume_mm3": bracket_mass_kg / DENSITY_T_MM3 / 1e3,
        "mesh": {"size_min": args.smin, "size_max": args.smax, "curvature": args.curv},
        "node_count": int(len(nodes)),
        "element_count": int(len(tets)),
        "mesh_time_s": round(nmesh, 1),
        "ccx_rc": int(rc),
        "solve_time_s": round(solve_time, 1),
        "n_modes_requested": args.modes,
        "frequencies_hz": freqs,
        "first_mode_hz": freqs[0] if freqs else None,
        "cases": {},
    }
    cg_id = len(nodes) + 1
    cg_prints = []
    import re as _re
    for m in _re.finditer(r"displacements \(vx,vy,vz\) for set CGNODE[^\n]*\n\s*\n?\s*(\S+)\s+(\S+)\s+(\S+)", dat_txt):
        cg_prints.append([float(m.group(1)), float(m.group(2)), float(m.group(3))])
    result["cg_prints_mm"] = cg_prints
    for i, (name, fx, fy, fz) in enumerate(CASES):
        db, sb, fb = cp.static_blocks(frd, args.modes, i)
        case = {"load_N": {"fx": fx, "fy": fy, "fz": fz}}
        if i < len(cg_prints):
            case["cg_disp_mm"] = cg_prints[i]
        elif db is not None:
            u = db["data"].get(cg_id)
            case["cg_disp_mm"] = None if u is None else [float(x) for x in u[:3]]
        if sb is not None:
            vm, vm_node, nvm = cp.max_von_mises(sb)
            case["max_von_mises_MPa"] = vm
            case["max_vm_node"] = vm_node
            case["yield_fos"] = YIELD_MPa / vm if vm and vm > 0 else None
            case["n_stress_nodes"] = nvm
        if fb is not None:
            rf = np.zeros(3)
            for nid in fix:
                v = fb["data"].get(int(nid))
                if v is not None and len(v) >= 3:
                    rf += v[:3]
            case["reaction_N"] = [float(x) for x in rf]
            # equilibrium: payload force + bracket inertia
            bracket_mass_kg = result.get("bracket_mass_kg")
            f_applied = np.array([fx, fy, fz])
            if bracket_mass_kg:
                acc = f_applied / PAYLOAD_KG  # mm/s^2
                f_applied = f_applied + bracket_mass_kg * 1e-3 * acc
            case["applied_total_N"] = [float(x) for x in f_applied]
            case["equilibrium_error_N"] = [float(f_applied[j] + rf[j]) for j in range(3)]
        result["cases"][name] = case
    (outdir / "summary.json").write_text(json.dumps(result, indent=2))
    print(json.dumps({k: result[k] for k in
                      ("node_count", "element_count", "ccx_rc", "solve_time_s",
                       "first_mode_hz", "frequencies_hz")}, indent=2))
    for name, case in result["cases"].items():
        print(name, "vm_max", case.get("max_von_mises_MPa"), "fos", case.get("yield_fos"),
              "cg", case.get("cg_disp_mm"))


if __name__ == "__main__":
    main()
