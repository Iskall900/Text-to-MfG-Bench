"""A15 bracket geometry builder (build123d).

Coordinate frame = A15.json global XYZ (the "setup frame"):
  - Telescope mounting plane: Z = 0 (base pads sit on it, material above Z=0)
  - Stage mounting plane:     Y = -7.164 (vertical plane, bracket material at Y > -7.164)
  - Three base bolts T1,T2,T3 (axis +Z), four stage bolts S1..S4 (axis +Y).

Usage:
    python3 bracket.py <outdir> [param_json]

Writes: bracket.step, bracket.stl, geometry_summary.json
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, asdict, field

from build123d import (
    Box, Cylinder, Pos, Axis, Plane, Polygon, Face, Wire, Edge, Vector,
    export_step, export_stl, Kind, offset, make_face, Location, Rot,
    fillet, chamfer, Part, Solid, Shape, Compound, Circle, Rectangle,
    extrude, loft, Sketch, GeomType,
)

# ----------------------------------------------------------------------------
# Interface data (mm) -- exact values from A15.json.  DO NOT CHANGE.
# ----------------------------------------------------------------------------
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

# 1/4 in NAS1352 socket head cap screw
SCREW_D = 6.35
CLEAR_D = 6.9        # normal clearance hole for 1/4" fastener
WASHER_D = 12.7      # NAS620 washer OD
SPOTFACE_D = 14.0    # bearing spot-face diameter
HEAD_D = 9.53        # socket head diameter
HEAD_H = 6.35


@dataclass
class Params:
    # base
    base_mode: str = "plate"   # "plate" or "spider"
    ped_h: float = 8.0
    ped_flare: float = 2.5
    ped_fill_h: float = 0.0   # fill rib notches in the pedestal
    pad_d: float = 22.0
    pad_h: float = 6.0
    arms: tuple = ()
    base_t: float = 4.5
    base_off: float = 13.0        # outward offset of base plate around T pads
    base_floor: float = 2.2       # floor thickness when pocketed
    base_rim: float = 8.0         # rim width of base pocket
    base_pocket: bool = True
    # stage plate (front structure)
    plate_t: float = 5.5
    plate_x: tuple = (-25.0, 22.0)
    plate_z: tuple = (100.0, 150.0)
    # ribs
    rib_t: float = 3.0
    rib_depth: float = 26.0       # depth in +Y from stage-plane back face
    rib_x: tuple = ((-25.0, -22.0), (-4.5, 1.5), (19.0, 22.0))
    # base flare
    flare: float = 3.0
    flare_h: float = 0.0
    # partial front wall / centre rib (start Z of the member)
    front_wall_z0: float = 0.0
    center_rib_z0: float = 0.0
    # base gussets: list of [attach_xy, target_xy, h0, h1, thickness, trim]
    gussets: tuple = ()
    # rear wall (closes the torsion cell)
    rear_wall: bool = True
    rear_wall_t: float = 3.0
    # top cap
    top_cap: bool = True
    cap_t: float = 2.5
    # keepout
    keepout_center: tuple = (79.4, 19.5)
    keepout_r: float = 70.0
    keepout_z: tuple = (-77.8, 31.4)
    apply_keepout: bool = True
    keepout_z_start: float = None   # exempt tie-down/base structure below this Z
    # fillets
    fillet_rib: float = 2.5
    fillet_base: float = 3.0
    # bosses
    boss: bool = False
    boss_d: float = 16.0
    boss_h: float = 2.0
    # rear access holes through top cap / rear structure
    rear_access: bool = False
    rear_access_d: float = 18.0


def _rounded_triangle(pts, off: float):
    """Outward offset (round corners) of the bolt polygon -> Sketch."""
    poly = Polygon(*pts, align=None)
    return offset(poly, amount=off, kind=Kind.ARC)


def build(p: Params) -> Part:
    """Prismatic rib tower + base plate.

    The tower is a Z-extrusion of an "E" cross-section (front wall = stage
    plate + 3 ribs), which is fully machinable from the +Y side.  A short
    drafted flare at the base improves the base joint.
    """
    x0, x1 = p.plate_x
    z1 = p.plate_z[1]
    yf = STAGE_PLANE_Y + p.plate_t       # back face of the stage wall

    # ---------------- tower cross-section (XY plane) ----------------
    cs = Pos((x0 + x1) / 2, STAGE_PLANE_Y + p.plate_t / 2) * \
        Rectangle(x1 - x0, p.plate_t)
    for (rx0, rx1) in p.rib_x:
        y0 = yf - 1.0                     # 1 mm overlap into the wall
        y1 = yf + p.rib_depth
        cs += Pos((rx0 + rx1) / 2, (y0 + y1) / 2) * \
            Rectangle(rx1 - rx0, y1 - y0)

    # fillet concave rib/wall corners (2D, robust)
    if p.fillet_rib > 0:
        vts = [v for v in cs.vertices() if abs(v.Y - yf) < 0.01]
        for r in (p.fillet_rib, p.fillet_rib * 0.8, 2.0):
            try:
                cs = fillet(vts, radius=r)
                break
            except Exception:
                vts = [v for v in cs.vertices() if abs(v.Y - yf) < 0.01]
                continue
        else:
            print("WARN cross-section rib fillet failed")
    # round the outer corners (tool-friendly) -- only convex vertices far
    # from other geometry; failures are tolerated
    try:
        cs = fillet(cs.vertices(), radius=2.0)
    except Exception as ex:
        pass

    # ---------------- base ----------------
    tower_z0 = p.base_t - 0.6
    if p.base_mode == "plate":
        tri = Polygon(*T_HOLES.values(), align=None)
        rect = Pos((x0 + x1) / 2, (STAGE_PLANE_Y + yf + p.rib_depth) / 2) * \
            Rectangle(x1 - x0, yf + p.rib_depth - STAGE_PLANE_Y)
        foot = tri + rect
        base_sk = offset(foot, amount=p.base_off, kind=Kind.ARC)
        base = extrude(base_sk, amount=p.base_t)
        if p.base_pocket:
            inner = offset(foot, amount=max(p.base_off - p.base_rim, 0.5),
                           kind=Kind.ARC)
            pocket = extrude(inner, amount=p.base_t + 2.0)
            keep = extrude(Pos(0, 0, -1.0) * offset(cs, amount=2.0,
                                                    kind=Kind.ARC),
                           amount=p.base_t + 4.0)
            pocket -= keep
            pocket = Pos(0, 0, p.base_floor) * pocket
            base -= pocket
        towersec = extrude(Pos(0, 0, tower_z0) * cs,
                           amount=z1 - tower_z0)
        part = base + towersec
    elif p.base_mode == "spider":
        tower_z0 = 0.0
        pedestal = extrude(offset(cs, amount=p.ped_flare, kind=Kind.ARC),
                           amount=p.ped_h)
        towersec = extrude(cs, amount=z1)
        part = pedestal + towersec
        if p.ped_fill_h > 0:
            # fill the two notches between the ribs (solid base block)
            rx = sorted(x for pair in p.rib_x for x in pair)
            for i in range(0, len(rx) - 2, 2):
                nx0, nx1 = rx[i + 1], rx[i + 2]
                fill = Box(nx1 - nx0, p.rib_depth, p.ped_fill_h)
                fill = Pos((nx0 + nx1) / 2,
                           yf + p.rib_depth / 2, p.ped_fill_h / 2) * fill
                part += fill
        for (tx, ty) in T_HOLES.values():
            pad = Pos(tx, ty, p.pad_h / 2) * Cylinder(p.pad_d / 2, p.pad_h)
            part += pad
    else:
        raise ValueError(p.base_mode)

    # ---------------- base taper/flare --------------------------------
    if p.flare_h > 0:
        big = offset(cs, amount=p.flare, kind=Kind.ARC)
        try:
            flare = loft([Pos(0, 0, tower_z0) * big,
                          Pos(0, 0, tower_z0 + p.flare_h) * cs])
            part += flare
        except Exception as ex:
            print("WARN flare loft failed:", str(ex)[:80])

    # ---------------- partial front wall (open frame below stage plate) ----
    if p.front_wall_z0 > p.base_t:
        zb = p.front_wall_z0
        z_lo = p.base_t - 0.1
        cutb = Box((x1 - x0) - 7.0, p.plate_t + 3.0, zb - z_lo)
        cutb = Pos((x0 + x1) / 2 - 0.5, STAGE_PLANE_Y + p.plate_t / 2,
                   (zb + z_lo) / 2) * cutb
        part -= cutb

    # ---------------- partial centre rib ----------------------------------
    if p.center_rib_z0 > p.base_t:
        crz = p.center_rib_z0
        crx = sorted(x for pair in p.rib_x for x in pair)
        cxm = (crx[2] + crx[3]) / 2 if len(crx) >= 4 else None
        if cxm is not None:
            z_lo = p.base_t - 0.1
            cutc = Box(8.0, p.rib_depth + 4.0, crz - z_lo)
            cutc = Pos(cxm, yf + p.rib_depth / 2 + 1.0,
                       (crz + z_lo) / 2) * cutc
            part -= cutc

    # ---------------- rear wall (torsion cell closure) ---------------------
    if p.rear_wall:
        rw = Box(x1 - x0, p.rear_wall_t, z1 - p.base_t + 0.6)
        rw = Pos((x0 + x1) / 2, yf + p.rib_depth - p.rear_wall_t / 2,
                 (p.base_t - 0.6 + z1) / 2) * rw
        part += rw

    # ---------------- base gussets -----------------------------------------
    from math import atan2, degrees, hypot
    for gspec in getattr(p, "gussets", ()) or ():
        (ax, ay), (tx, ty), h0, h1, th = gspec[:5]
        trim = gspec[5] if len(gspec) > 5 else 9.0
        L = hypot(tx - ax, ty - ay)
        ang = degrees(atan2(ty - ay, tx - ax))
        Lg = L - trim
        z0 = p.base_t - 0.6
        pts = [(0, 0), (0, h0), (Lg, h1), (Lg, 0)]
        prof = Polygon(*pts, align=None)
        sol = extrude(prof, amount=th)
        sol = Rot(90, 0, 0) * sol          # stand upright (thickness in -Y)
        sol = Pos(0, th / 2, 0) * sol      # center on the axis
        sol = Pos(ax, ay, z0) * (Rot(0, 0, ang) * sol)
        part += sol

    # ---------------- spider arms (base tie-down) -------------------------
    if p.base_mode == "spider":
        from math import atan2, degrees, hypot
        for spec in p.arms:
            (ax, ay), (tx, ty), h0, h1, th = spec[:5]
            trim = spec[5] if len(spec) > 5 else 7.0
            L = hypot(tx - ax, ty - ay)
            ang = degrees(atan2(ty - ay, tx - ax))
            Lg = L - trim
            pts = [(0, 0), (0, h0), (Lg, h1), (Lg, 0)]
            prof = Polygon(*pts, align=None)
            sol = extrude(prof, amount=th)
            sol = Rot(90, 0, 0) * sol
            sol = Pos(0, th / 2, 0) * sol
            sol = Pos(ax, ay, 0.4) * (Rot(0, 0, ang) * sol)
            part += sol

    # ---------------- top cap ---------------------------------------------
    if p.top_cap:
        rxlo = min(a for a, b in p.rib_x)
        rxhi = max(b for a, b in p.rib_x)
        cap = Box(rxhi - rxlo, p.rib_depth, p.cap_t)
        cap = Pos((rxlo + rxhi) / 2, yf + p.rib_depth / 2,
                  z1 - p.cap_t / 2) * cap
        part += cap
        try:
            edges = [e for e in part.edges()
                     if e.geom_type == GeomType.LINE
                     and abs(e.center().Z - (z1 - p.cap_t)) < 0.01
                     and e.center().Y > yf + 0.01]
            part = _try_fillet(part, edges, min(2.5, p.cap_t), "cap")
        except Exception as ex:
            print("WARN cap fillet:", ex)

    # ---------------- keepout cylinder cut (above base plate) --------------
    if p.apply_keepout:
        kx, ky = p.keepout_center
        z_lo, z_hi = p.keepout_z
        h = (z_hi - z_lo) + 4.0
        cut = Cylinder(p.keepout_r, h)
        cut = Pos(kx, ky, (z_lo + z_hi) / 2) * cut
        zc = p.base_t + 0.5 if p.keepout_z_start is None else p.keepout_z_start
        cut = cut & (Pos(0, 0, zc + 250) * Box(900, 900, 500))
        part -= cut

    # ---------------- bolt holes ------------------------------------------
    for (tx, ty) in T_HOLES.values():
        hh = (p.pad_h if p.base_mode == "spider" else p.base_t) + 6
        hole = Cylinder(CLEAR_D / 2, hh)
        hole = Pos(tx, ty, hh / 2 - 3 + 1.0) * hole
        part -= hole
    for (sx, sz) in S_HOLES.values():
        hole = Cylinder(CLEAR_D / 2, p.plate_t + 20)
        hole = Pos(sx, STAGE_PLANE_Y + p.plate_t / 2, sz) * Rot(90, 0, 0) * hole
        part -= hole
        sf = Cylinder(SPOTFACE_D / 2, 2.0)
        sf = Pos(sx, yf - 1.0, sz) * Rot(90, 0, 0) * sf
        part -= sf

    # ---------------- rear access holes (rear wall only) -------------------
    if p.rear_access and p.rear_wall:
        for (sx, sz) in S_HOLES.values():
            h = Cylinder(p.rear_access_d / 2, p.rear_wall_t + 8)
            h = Pos(sx, yf + p.rib_depth - p.rear_wall_t / 2, sz) * \
                Rot(90, 0, 0) * h
            part -= h

    # ---------------- deburr bottom perimeter ------------------------------
    try:
        be = [e for e in part.edges()
              if e.geom_type == GeomType.LINE and abs(e.center().Z) < 1e-6
              and e.length > 1.0]
        if be:
            part = chamfer(be, length=0.4)
    except Exception as ex:
        print("WARN chamfer failed:", str(ex)[:60])

    return part


def _try_fillet(part: Part, edges, radius: float, tag: str) -> Part:
    edges = [e for e in edges if e is not None]
    if not edges:
        print(f"WARN {tag} fillet: no edges selected")
        return part
    for r in (radius, radius * 0.75, radius * 0.5, 1.0):
        try:
            out = fillet(edges, radius=r)
            return out
        except Exception:
            continue
    print(f"WARN {tag} fillet failed for all radii")
    return part


def summarize(part: Part, p: Params) -> dict:
    density = 2.70e-9  # tonne/mm^3
    vol = part.volume
    bb = part.bounding_box()
    return {
        "volume_mm3": vol,
        "mass_kg": vol * density * 1000.0,
        "bbox_min": [bb.min.X, bb.min.Y, bb.min.Z],
        "bbox_max": [bb.max.X, bb.max.Y, bb.max.Z],
        "params": asdict(p),
    }


def main():
    outdir = sys.argv[1]
    os.makedirs(outdir, exist_ok=True)
    p = Params()
    if len(sys.argv) > 2:
        with open(sys.argv[2]) as f:
            d = json.load(f)
        for k, v in d.items():
            if not hasattr(p, k):
                raise KeyError(f"unknown param {k}")
            if isinstance(getattr(p, k), tuple) and isinstance(v, list):
                if v and isinstance(v[0], list):
                    v = tuple(tuple(x) for x in v)
                else:
                    v = tuple(v)
            setattr(p, k, v)
    part = build(p)
    part.label = "A15_bracket"
    export_step(part, os.path.join(outdir, "bracket.step"))
    export_stl(part, os.path.join(outdir, "bracket.stl"),
               tolerance=0.05, angular_tolerance=0.2)
    s = summarize(part, p)
    with open(os.path.join(outdir, "geometry_summary.json"), "w") as f:
        json.dump(s, f, indent=2)
    print(json.dumps({k: v for k, v in s.items() if k != "params"}, indent=2))
    print("solid count:", len(part.solids()))


if __name__ == "__main__":
    main()
