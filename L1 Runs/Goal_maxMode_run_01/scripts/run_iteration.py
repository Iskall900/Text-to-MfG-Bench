"""Run a full design iteration: geometry -> mesh -> decks -> ccx -> results.

Usage:  python3 run_iteration.py <N> <params.json> [--modal-only]

Creates/uses iteration<N>/{DfM<N>,geometry<N>,FEA<N>}
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time

import numpy as np
from build123d import import_step, Cylinder, Pos, Box, export_step

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def run(cmd, cwd=None, log=None):
    t0 = time.time()
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    dt = time.time() - t0
    if log:
        with open(log, "a") as f:
            f.write(f"\n$ {' '.join(cmd)}  ({dt:.1f}s, rc={r.returncode})\n")
            f.write(r.stdout[-4000:])
            f.write(r.stderr[-2000:])
    if r.returncode != 0:
        print(f"  ! command failed rc={r.returncode}: {' '.join(cmd)}")
        print(r.stdout[-1500:])
        print(r.stderr[-1500:])
    return r, dt


def keepout_volume(part):
    from build123d import Cylinder as C, Pos as P
    k = P(79.4, 19.5, -23.2) * C(70.0, 109.2 + 4.0)
    return (part & k).volume


def main():
    n = int(sys.argv[1])
    params_path = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("-") else None
    it = os.path.join(ROOT, f"iteration{n}")
    geo = os.path.join(it, f"geometry{n}")
    fea = os.path.join(it, f"FEA{n}")
    dfm = os.path.join(it, f"DfM{n}")
    for d in (it, geo, fea, dfm):
        os.makedirs(d, exist_ok=True)

    if params_path:
        shutil.copy(params_path, os.path.join(geo, "params.json"))

    # ---- geometry ----
    print(f"[iteration{n}] building geometry ...")
    args = [sys.executable, os.path.join(ROOT, "scripts", "bracket.py"), geo]
    if params_path:
        args.append(params_path)
    r, _ = run(args, cwd=ROOT)
    with open(os.path.join(geo, "geometry_summary.json")) as f:
        gsum = json.load(f)
    print(f"  volume={gsum['volume_mm3']:.0f} mm3 mass={gsum['mass_kg']*1000:.1f} g")

    # ---------------- mesh ----------------
    meta_path = os.path.join(fea, "mesh_meta.json")
    if not os.path.exists(meta_path) or "--remesh" in sys.argv:
        print(f"[iteration{n}] meshing ...")
        for ho, alg in ((2, 10), (1, 10), (0, 10), (1, 1), (0, 1)):
            r, dt = run([sys.executable, os.path.join(ROOT, "scripts",
                         "mesh_model.py"), os.path.join(geo, "bracket.step"),
                         fea, "2.8", "0.8", str(ho), str(alg)], cwd=ROOT)
            if os.path.exists(meta_path):
                break
        if not os.path.exists(meta_path):
            raise RuntimeError("meshing failed for all gmsh options")
        print(f"  mesh done in {dt:.0f}s")
    with open(meta_path) as f:
        meta = json.load(f)
    print(f"  nodes={meta['n_nodes']} elems={meta['n_elem']}")

    # ---------------- decks ----------------
    run([sys.executable, os.path.join(ROOT, "scripts", "build_decks.py"), fea], cwd=ROOT)

    # ---------------- mesh validation (static probe, free) ----------------
    def probe_ok(txt):
        bad = ("nonpositive jacobian" in txt or
               "at least one fatal" in txt or
               "Job finished" not in txt)
        return not bad

    probe = "static_Xp"
    for ext in (".dat", ".frd", ".sta", ".cvg", ".12d"):
        p_ = os.path.join(fea, probe + ext)
        if os.path.exists(p_):
            os.remove(p_)
    r, _ = run(["ccx", "-i", probe], cwd=fea)
    if not probe_ok(r.stdout):
        for attempt, (mx, mn) in enumerate((("3.0", "1.2"), ("3.6", "1.5")), 1):
            print(f"  ! mesh validation failed; remesh attempt {attempt}")
            shutil.rmtree(fea)
            os.makedirs(fea)
            run([sys.executable, os.path.join(ROOT, "scripts", "mesh_model.py"),
                 os.path.join(geo, "bracket.step"), fea, mx, mn], cwd=ROOT)
            run([sys.executable, os.path.join(ROOT, "scripts", "build_decks.py"),
                 fea], cwd=ROOT)
            r, _ = run(["ccx", "-i", probe], cwd=fea)
            if probe_ok(r.stdout):
                break
    print("  mesh validation ok" if probe_ok(r.stdout)
          else "  ! MESH STILL INVALID - aborting before modal")
    if not probe_ok(r.stdout):
        return

    # ---------------- ccx runs ----------------
    print(f"[iteration{n}] static runs ...")
    static_results = {}
    for case in ("Xp", "Xn", "Yp", "Yn", "Zp", "Zn"):
        lbl = f"static_{case}"
        for ext in (".dat", ".frd", ".sta", ".cvg"):
            p = os.path.join(fea, lbl + ext)
            if os.path.exists(p):
                os.remove(p)
        r, dt = run(["ccx", "-i", lbl], cwd=fea,
                    log=os.path.join(fea, "run_log.txt"))
        dp = os.path.join(fea, lbl + ".dat")
        if os.path.exists(dp):
            out, _ = run([sys.executable, os.path.join(ROOT, "scripts",
                         "parse_results.py"), ".", lbl], cwd=fea)
            static_results[case] = json.load(
                open(os.path.join(fea, f"results_{lbl}.json")))

    # ---------------- modal ----------------
    modal_res = {}
    dat = os.path.join(fea, "modal.dat")
    if not os.path.exists(dat) or "--remodal" in sys.argv:
        print(f"[iteration{n}] modal run ...")
        r, dt = run(["ccx", "-i", "modal"], cwd=fea,
                    log=os.path.join(fea, "run_log.txt"))
    if os.path.exists(dat):
        txt = open(dat, errors="ignore").read()
        freqs = []
        import re
        me = re.search(r"E I G E N V A L U E\s+O U T P U T(.*?)P A R T I C I P A T I O N",
                       txt, re.S)
        if me:
            for line in me.group(1).splitlines():
                parts = line.split()
                if len(parts) >= 4 and parts[0].isdigit():
                    freqs.append(float(parts[3]))
        modal_res["frequencies_Hz"] = freqs
        modal_res["f1_Hz"] = freqs[0] if freqs else None

    # ---------------- combine ----------------
    keep_vol = keepout_volume(import_step(os.path.join(geo, "bracket.step")))
    # DfM note
    bb = gsum["bbox_min"], gsum["bbox_max"]
    stock = [round(b - a + 10, 1) for a, b in zip(bb[0], bb[1])]
    with open(os.path.join(dfm, "DfM_notes.md"), "w") as f:
        f.write(f"# DfM notes - iteration {n}\n\n")
        f.write(f"- stock billet (min bounding + 10 mm): {stock[0]} x {stock[1]}"
                f" x {stock[2]} mm (6061-T651)\n")
        f.write("- fixtures/features: see geometry summary\n")
        f.write(f"- mass: {gsum['mass_kg']*1000:.1f} g\n")
    
    summary = {
        "iteration": n,
        "geometry": {k: v for k, v in gsum.items() if k != "params"},
        "mesh": meta,
        "modal": modal_res,
        "static": static_results,
        "keepout_intersection_volume_mm3": keep_vol,
    }
    with open(os.path.join(it, f"results_iteration{n}.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps({
        "iteration": n,
        "mass_kg": gsum["mass_kg"],
        "f1_Hz": modal_res.get("f1_Hz"),
        "modes": modal_res.get("frequencies_Hz", [])[:4],
        "keepout_mm3": keep_vol,
        "max_vm": {k: v.get("max_vm_MPa") for k, v in static_results.items()},
        "cg": static_results.get("Xp", {}).get("cg_disp"),
    }, indent=2))


if __name__ == "__main__":
    main()
