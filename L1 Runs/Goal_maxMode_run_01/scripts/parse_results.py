"""Parse CalculiX .frd / .dat output into a compact JSON summary."""
from __future__ import annotations

import json
import os
import re
import sys

import numpy as np


def parse_dat_reactions(dat_path):
    """Return (reaction totals, cg displacement) from .dat."""
    if not os.path.exists(dat_path):
        return None
    txt = open(dat_path, errors="ignore").read()
    out = {}
    m = re.search(r"total force \(fx,fy,fz\) for set FIX[^\n]*\n\n\s*"
                  r"([-\d.E+]+)\s+([-\d.E+]+)\s+([-\d.E+]+)", txt)
    if m:
        out["reaction_total"] = [float(m.group(i)) for i in (1, 2, 3)]
    m = re.search(r"displacements \(vx,vy,vz\) for set CG[^\n]*\n\n\s*"
                  r"\d+\s+([-\d.Ee+]+)\s+([-\d.Ee+]+)\s+([-\d.Ee+]+)", txt)
    if m:
        out["cg_disp"] = [float(m.group(i)) for i in (1, 2, 3)]
    m = re.search(r"displacements \(vx,vy,vz\) for set CG[^\n]*\n\n\s*"
                  r"\d+\s+([-\d.Ee+]+)\s+([-\d.Ee+]+)\s+([-\d.Ee+]+)\s+"
                  r"([-\d.Ee+]+)\s+([-\d.Ee+]+)\s+([-\d.Ee+]+)", txt)
    return out


def parse_frd(path, want=("DISP", "STRESS")):
    """Return dict with node displacements and nodal von Mises stresses."""
    disp = {}
    stress = {}
    cur = None
    curcomp = None
    with open(path, errors="ignore") as f:
        for line in f:
            if line.startswith(" -4"):
                cur = line.split()[1] if len(line.split()) > 1 else None
                curcomp = None
                continue
            if line.startswith(" -5"):
                continue
            if line.startswith(" -1") or line.startswith(" -2"):
                nums = re.findall(
                    r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[Ee][-+]?\d+)?",
                    line[3:])
                if cur == "DISP" and len(nums) >= 4:
                    try:
                        disp[int(float(nums[0]))] = (
                            float(nums[1]), float(nums[2]), float(nums[3]))
                    except ValueError:
                        pass
                elif cur == "STRESS" and len(nums) >= 7:
                    try:
                        stress[int(float(nums[0]))] = [float(v)
                                                       for v in nums[1:7]]
                    except ValueError:
                        pass
            if line.startswith(" -3"):
                cur = None
    return disp, stress


def von_mises(s):
    sxx, syy, szz, sxy, syz, szx = s
    return np.sqrt(0.5 * ((sxx - syy) ** 2 + (syy - szz) ** 2 +
                          (szz - sxx) ** 2) +
                   3.0 * (sxy ** 2 + syz ** 2 + szx ** 2))


def main():
    feadir = sys.argv[1]
    label = sys.argv[2]
    dat = os.path.join(feadir, f"{label}.dat")
    frd = os.path.join(feadir, f"{label}.frd")
    out = {"label": label}
    r = parse_dat_reactions(dat)
    if r:
        out.update(r)
    disp, stress = parse_frd(frd)
    if disp:
        u = np.array([disp[k] for k in sorted(disp)])
        out["n_disp"] = len(disp)
        out["max_disp_mm"] = float(np.linalg.norm(u, axis=1).max())
        out["max_disp_comp"] = [float(x) for x in
                                np.abs(u).max(axis=0)]
    if stress:
        vm = {k: von_mises(np.array(v)) for k, v in stress.items()}
        keys = sorted(vm)
        vals = np.array([vm[k] for k in keys])
        out["n_stress_nodes"] = len(keys)
        out["max_vm_MPa"] = float(vals.max())
        out["vm_p999_MPa"] = float(np.quantile(vals, 0.999))
        out["vm_p99_MPa"] = float(np.quantile(vals, 0.99))
        # location of max stress
        km = keys[int(np.argmax(vals))]
        out["max_vm_node"] = km
    with open(os.path.join(feadir, f"results_{label}.json"), "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
