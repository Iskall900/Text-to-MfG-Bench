"""Parametric bracket model for A15 (v1 family), staged construction.

Units mm. Interfaces from A15.json:
  T1,T2,T3: holes along +Z at z=0, telescope plane
  S1..S4 : holes along +Y at y = PLANE_Y (stage/payload mounting plane)
Payload CG at CG. Bracket body kept at y >= PLANE_Y, z >= 0.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from build123d import (
    Align, Box, Cylinder, Kind, Plane, Polygon, Polyline, Pos, Rectangle, Rot, Vector,
    export_step, export_stl, extrude, fillet, loft, make_face, offset,
)

PLANE_Y = -7.164
D_BOLT = 6.7
T_HOLES = [(30.03, -21.45), (30.03, 42.047), (-58.86, 42.047)]
S_HOLES = [(11.075, 112.51), (-14.32, 112.51), (-14.32, 137.91), (11.075, 137.91)]
CG = (-1.6225, -57.164, 125.21)


@dataclass
class Params:
    # base
    base_t: float = 4.0
    pad: float = 26.0
    arm_w: float = 16.0
    hub_x: tuple = (-1.6225, -1.6225)
    hub_y: tuple = (8.9, 8.9)
    hub_r: float = 30.0
    base_bolt_r: float = D_BOLT / 2
    base_round_r: float = 3.0     # vertical fillet radius at arm/hub junctions
    # tower
    tower_xc: float = -1.6225
    tower_z1: float = 103.0
    tower_w0: float = 48.0
    tower_w1: float = 48.0
    z_straight: float = 88.0
    tf: float = 2.4
    tw: float = 2.8
    y_back: float = 25.0
    web_holes: int = 3
    web_hole_r: float = 6.0
    # interface plate
    plate_t: float = 7.5
    plate_z: tuple = (103.0, 148.0)
    plate_ribs: bool = False
    rib_t: float = 2.6
    rib_depth: float = 10.0
    web_extend: bool = True
    side_fins: bool = False
    side_fin_t: float = 2.6
    side_fin_depth: float = 12.0
    back_skin: bool = False
    back_t: float = 3.0
    back_top_z: float = 103.0
    back_windows: bool = False
    shelf_zs: tuple = ()
    shelf_t: float = 2.8
    side_walls: bool = False
    sw_t: float = 2.6
    sw_window_y: tuple = (-2.0, 20.0)
    sw_window_z: tuple = (18.0, 90.0)
    base_slots: bool = False
    slot_margin: float = 0.0
    base_ribs: bool = False
    # fillets
    r_core: float = 1.5
    r_base_fillet: float = 4.0
    payload_kg: float = 1.35

    @property
    def plate_x(self):
        half = self.tower_w1 / 2
        return (self.tower_xc - half, self.tower_xc + half)


def _rounded_rect(cx, cy, w, h, r):
    f = Pos(cx, cy, 0) * Rectangle(w - 2 * r, h - 2 * r,
                                   align=(Align.CENTER, Align.CENTER))
    return offset(f, r, kind=Kind.ARC)


def build_base(p: Params):
    hx = (p.hub_x[0] + p.hub_x[1]) / 2
    hy = (p.hub_y[0] + p.hub_y[1]) / 2
    base = Pos(hx, hy, p.base_t / 2) * Cylinder(p.hub_r, p.base_t)
    for (x, y) in T_HOLES:
        d = np.array([x - hx, y - hy])
        L = np.linalg.norm(d)
        ang = np.degrees(np.arctan2(d[1], d[0]))
        arm = Pos(hx + d[0] / 2, hy + d[1] / 2, p.base_t / 2) * Rot(0, 0, ang) * Box(
            L, p.arm_w, p.base_t)
        pad = Pos(x, y, p.base_t / 2) * Cylinder(p.pad / 2, p.base_t)
        base = base + arm + pad
    base = fillet_incremental(base, (p.base_round_r, 2.5, 2.0, 1.5, 1.2, 1.0))
    if p.base_slots and p.side_walls:
        px0, px1 = p.plate_x
        m = p.slot_margin
        y0, y1 = PLANE_Y + p.tf + m, p.y_back - p.tf - m
        for x0, x1 in ((px0 + p.sw_t + m, p.tower_xc - p.tw / 2 - m),
                       (p.tower_xc + p.tw / 2 + m, px1 - p.sw_t - m)):
            if x1 > x0 and y1 > y0:
                slot = Pos((x0 + x1) / 2, (y0 + y1) / 2, p.base_t / 2) * Box(
                    x1 - x0, y1 - y0, p.base_t * 4)
                base = base - slot
    for (x, y) in T_HOLES:
        base = base - Pos(x, y, p.base_t / 2) * Cylinder(p.base_bolt_r, p.base_t * 4)
    return base


def build_base_ribs(p: Params):
    """Ladder-frame base: strips under flanges/web + arms + pads (cells open below)."""
    t = p.base_t
    x0 = p.tower_xc - p.tower_w1 / 2 - 2.0
    x1 = p.tower_xc + p.tower_w1 / 2 + 2.0
    yf = PLANE_Y - 2.0
    yb = p.y_back + 2.0
    parts = []
    # front strip, back strip, middle strip (under web)
    parts.append(Pos((x0 + x1) / 2, yf + 2.55, t / 2) * Box(x1 - x0, 5.1, t))
    parts.append(Pos((x0 + x1) / 2, yb - 2.6, t / 2) * Box(x1 - x0, 5.2, t))
    parts.append(Pos(p.tower_xc, (yf + yb) / 2, t / 2) * Box(6.0, yb - yf, t))
    # end ribs under the side walls (close the ladder frame, keep cells open)
    parts.append(Pos(x0 + p.sw_t / 2, (yf + yb) / 2, t / 2) * Box(p.sw_t, yb - yf, t))
    parts.append(Pos(x1 - p.sw_t / 2, (yf + yb) / 2, t / 2) * Box(p.sw_t, yb - yf, t))
    base = parts[0]
    for q in parts[1:]:
        base = base + q
    for (x, y) in T_HOLES:
        # arm from nearest strip to pad
        ax = min(max(x, x0 + 3.0), x1 - 3.0)
        anchor = (ax, yf + 2.55) if y < (yf + yb) / 2 else (ax, yb - 2.6)
        d = np.array([x - anchor[0], y - anchor[1]])
        L = np.linalg.norm(d)
        ang = np.degrees(np.arctan2(d[1], d[0]))
        arm = Pos(anchor[0] + d[0] / 2, anchor[1] + d[1] / 2, t / 2) * Rot(0, 0, ang) * Box(
            L, p.arm_w, t)
        pad = Pos(x, y, t / 2) * Cylinder(p.pad / 2, t)
        base = base + arm + pad
    base = fillet_incremental(base, (p.base_round_r, 2.5, 2.0, 1.5, 1.2, 1.0))
    for (x, y) in T_HOLES:
        base = base - Pos(x, y, t / 2) * Cylinder(p.base_bolt_r, t * 4)
    return base


def build_tower(p: Params):
    z0, z1, zs = p.base_t, p.tower_z1, p.z_straight
    w0, w1 = p.tower_w0, p.tower_w1
    xc = p.tower_xc
    # flange side profile in X-Z plane (trapezoid + straight section)
    pts = [(xc - w0 / 2, z0), (xc - w1 / 2, zs), (xc - w1 / 2, z1),
           (xc + w1 / 2, z1), (xc + w1 / 2, zs), (xc + w0 / 2, z0)]
    prof = Plane.XZ * make_face(Polyline(*pts, close=True))
    flanges = []
    for y0 in (PLANE_Y, p.y_back - p.tf):
        flanges.append(extrude(Pos(0, y0 + p.tf, 0) * prof, p.tf))
    depth = p.y_back - PLANE_Y
    zw = p.plate_z[1] if p.web_extend else z1
    web = Pos(p.tower_xc, PLANE_Y + depth / 2, (z0 + z1) / 2) * Box(
        p.tw, depth, z1 - z0)
    tower = flanges[0] + flanges[1] + web
    if p.web_extend:
        fin = Pos(p.tower_xc, PLANE_Y + depth / 2, (z1 + zw) / 2) * Box(
            p.tw, depth, zw - z1)
        tower = tower + fin
    if p.side_fins:
        px0, px1 = p.plate_x
        y0 = PLANE_Y
        y1 = PLANE_Y + p.side_fin_depth
        for x0 in (px0, px1 - p.side_fin_t):
            sf = Pos(x0 + p.side_fin_t / 2, (y0 + y1) / 2, (z1 + zw) / 2) * Box(
                p.side_fin_t, y1 - y0, zw - z1)
            tower = tower + sf
    if p.side_walls:
        px0, px1 = p.plate_x
        y0 = PLANE_Y
        y1 = p.y_back
        for x0 in (px0, px1 - p.sw_t):
            wall = Pos(x0 + p.sw_t / 2, (y0 + y1) / 2, (z0 + zw) / 2) * Box(
                p.sw_t, y1 - y0, zw - z0)
            wy0, wy1 = p.sw_window_y
            wz0, wz1 = p.sw_window_z
            if wz1 > wz0 and wy1 > wy0:
                wr = min(4.0, (wy1 - wy0) / 2 - 0.1, (wz1 - wz0) / 2 - 0.1)
                wprof = Pos((wy0 + wy1) / 2, (wz0 + wz1) / 2, 0) * Rectangle(
                    wy1 - wy0 - 2 * wr, wz1 - wz0 - 2 * wr,
                    align=(Align.CENTER, Align.CENTER))
                wprof = offset(wprof, wr, kind=Kind.ARC)
                wplane = Plane(origin=(x0 + p.sw_t / 2, 0, 0),
                               x_dir=(0, 1, 0), z_dir=(1, 0, 0))
                win = extrude(wplane * wprof, p.sw_t, both=True)
                wall = wall - win
            tower = tower + wall
    for zc in p.shelf_zs:
        sh = Pos(p.tower_xc, PLANE_Y + depth / 2, zc) * Box(
            p.tower_w1, depth, p.shelf_t)
        tower = tower + sh
    if p.back_skin:
        px0, px1 = p.plate_x
        y1 = p.y_back
        y0 = y1 - p.back_t
        zt = p.back_top_z
        skin = Pos((px0 + px1) / 2, (y0 + y1) / 2, (zt + zw) / 2) * Box(
            px1 - px0, y1 - y0, zw - zt)
        tower = tower + skin
        if p.back_windows:
            xa, xb = px0 + p.side_fin_t, p.tower_xc - p.tw / 2
            xc2, xd = p.tower_xc + p.tw / 2, px1 - p.side_fin_t
            za, zb = zt + 8.0, zw - 8.0
            for xa2, xb2 in ((xa, xb), (xc2, xd)):
                win = Pos((xa2 + xb2) / 2, (y0 + y1) / 2, (za + zb) / 2) * Box(
                    (xb2 - xa2), (y1 - y0) * 4, (zb - za))
                tower = tower - win
    tower = fillet_incremental(tower, (p.r_core, 1.5, 1.2, 1.0))
    if p.web_holes:
        zs_h = np.linspace(z0 + 20, z1 - 20, p.web_holes + 2)[1:-1]
        for zc in zs_h:
            hole = Pos(p.tower_xc, (PLANE_Y + p.y_back) / 2, zc) * Rot(0, 90, 0) * Cylinder(
                p.web_hole_r, p.tw * 4)
            tower = tower - hole
    return tower


def build_plate(p: Params):
    px0, px1 = p.plate_x
    pz0, pz1 = p.plate_z
    plate = Pos((px0 + px1) / 2, PLANE_Y + p.plate_t / 2, (pz0 + pz1) / 2) * Box(
        px1 - px0, p.plate_t, pz1 - pz0)
    if p.plate_ribs:
        # rib profile in X-Z (u=x, v=z) built on Plane.XZ; extrusion goes -Y.
        y0 = PLANE_Y + p.plate_t
        rt = p.rib_t
        rects = []
        W = px1 - px0
        H = pz1 - pz0
        # left, right, bottom, top perimeter ribs (inside edges)
        rects.append(Pos(px0 + rt / 2, (pz0 + pz1) / 2, 0) * Rectangle(rt, H))
        rects.append(Pos(px1 - rt / 2, (pz0 + pz1) / 2, 0) * Rectangle(rt, H))
        rects.append(Pos((px0 + px1) / 2, pz0 + rt / 2, 0) * Rectangle(W, rt))
        rects.append(Pos((px0 + px1) / 2, pz1 - rt / 2, 0) * Rectangle(W, rt))
        # central cross
        rects.append(Pos(p.tower_xc, (pz0 + pz1) / 2, 0) * Rectangle(rt, H))
        rects.append(Pos((px0 + px1) / 2, 125.21, 0) * Rectangle(W, rt))
        prof = Plane.XZ * rects[0]
        for r in rects[1:]:
            prof = prof + (Plane.XZ * r)
        rib = extrude(Pos(0, y0 + p.rib_depth, 0) * prof, p.rib_depth)
        plate = plate + rib
    for (x, z) in S_HOLES:
        plate = plate - Pos(x, PLANE_Y + p.plate_t / 2, z) * Rot(90, 0, 0) * Cylinder(
            p.base_bolt_r, p.plate_t * 4)
    return plate


def build(p: Params = Params()):
    base = build_base_ribs(p) if p.base_ribs else build_base(p)
    tower = build_tower(p)
    top = tower + build_plate(p)
    bracket = base + top
    # stage 1: base <-> tower junction (edges at z ~ base_t)
    for r in (p.r_base_fillet, 3.0, 2.5, 2.0, 1.5, 1.2, 1.0):
        ce = [e for e in concave_edges(bracket)
              if abs(e.position_at(0.5).Z - p.base_t) < 0.8]
        if not ce:
            break
        try:
            bracket = fillet(ce, r)
            break
        except Exception:
            pass
    # stage 2: tower <-> plate junction (edges at z ~ tower_z1)
    for r in (p.r_core, 1.5, 1.2, 1.0):
        ce = [e for e in concave_edges(bracket)
              if e.position_at(0.5).Z > p.tower_z1 - 0.8]
        if not ce:
            break
        try:
            bracket = fillet(ce, r)
            break
        except Exception:
            pass
    # stage 3: anything left
    bracket = fillet_incremental(bracket)
    return bracket


def round_vertical_concave(part, r, z0=None, z1=None, tol=1e-3):
    """Round vertical concave edges by unioning tangent cylinders spanning [z0,z1]."""
    if z0 is None or z1 is None:
        bb = part.bounding_box()
        z0, z1 = bb.min.Z, bb.max.Z
    for e in concave_edges(part):
        t = e.tangent_at(0.5)
        if abs(abs(t.Z) - 1.0) > 1e-3:
            continue
        pm = e.position_at(0.5)
        # find the two adjacent faces
        faces = [f for f in part.faces() if e in f.edges()]
        if len(faces) != 2:
            continue
        n1 = faces[0].normal_at(pm)
        n2 = faces[1].normal_at(pm)
        n1 = Vector(n1.X, n1.Y, 0)
        n2 = Vector(n2.X, n2.Y, 0)
        if n1.length < 1e-9 or n2.length < 1e-9:
            continue
        n1 = n1.normalized()
        n2 = n2.normalized()
        cosang = max(-1.0, min(1.0, n1.dot(n2)))
        ang = np.arccos(cosang)
        if ang < 1e-6:
            continue
        bis = -(n1 + n2)
        if bis.length < 1e-9:
            continue
        bis = bis.normalized()
        center_dist = r / np.cos(ang / 2)
        c = pm + bis * center_dist
        cyl = Pos(c.X, c.Y, (z0 + z1) / 2) * Cylinder(r, z1 - z0)
        part = part + cyl
    return part


def fillet_incremental(part, radii=(2.5, 2.0, 1.5, 1.2, 1.0), max_iter=400):
    """Fillet concave edges one at a time (longest first), shrinking radius as needed."""
    import time as _time
    for r in radii:
        for _ in range(max_iter):
            ce = concave_edges(part)
            if not ce:
                return part
            applied = False
            for e in sorted(ce, key=lambda x: -x.length):
                try:
                    part = fillet([e], r)
                    applied = True
                    break
                except Exception:
                    continue
            if not applied:
                break
    return part


def try_fillet(part, r):
    """Fillet all concave edges, with shrinking radius fallback."""
    for radius in (r, 0.8 * r, 0.6 * r, 0.45 * r):
        try:
            ce = concave_edges(part)
            if not ce:
                return part
            return fillet(ce, radius)
        except Exception:
            continue
    return part


def concave_edges(part):
    """Concave edges via signed dihedral test (validated on L-shape)."""
    faces = part.faces()
    out = []
    for e in part.edges():
        fs = [f for f in faces if e in f.edges()]
        if len(fs) != 2:
            continue
        try:
            pmid = e.position_at(0.5)
            n1 = fs[0].normal_at(pmid)
            n2 = fs[1].normal_at(pmid)
            t = e.tangent_at(0.5)
        except Exception:
            continue
        if n1.cross(n2).dot(t) > 1e-9:
            out.append(e)
    return out


def mass_g(part):
    return part.volume * 2.7e-3  # mm^3 -> g
