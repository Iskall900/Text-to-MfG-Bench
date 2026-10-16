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
    # fillets
    r_core: float = 1.5
    payload_kg: float = 1.35

    @property
    def plate_x(self):
        half = self.tower_w1 / 2
        return (self.tower_xc - half, self.tower_xc + half)


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
    base = try_fillet(base, p.base_round_r)
    for (x, y) in T_HOLES:
        base = base - Pos(x, y, p.base_t / 2) * Cylinder(p.base_bolt_r, p.base_t * 4)
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
    web = Pos(p.tower_xc, PLANE_Y + depth / 2, (z0 + zw) / 2) * Box(
        p.tw, depth, zw - z0)
    tower = flanges[0] + flanges[1] + web
    tower = try_fillet(tower, p.r_core)
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
    base = build_base(p)
    tower = build_tower(p)
    top = tower + build_plate(p)
    bracket = base + top
    # stage 1: base <-> tower junction (edges at z ~ base_t)
    for r in (p.r_core, 1.2, 1.0, 0.8, 0.6):
        try:
            ce = [e for e in concave_edges(bracket)
                  if abs(e.position_at(0.5).Z - p.base_t) < 0.6]
            if ce:
                bracket = fillet(ce, r)
            break
        except Exception:
            continue
    # stage 2: tower <-> plate junction (edges at z ~ tower_z1)
    for r in (p.r_core, 1.2, 1.0, 0.8, 0.6):
        try:
            ce = [e for e in concave_edges(bracket)
                  if e.position_at(0.5).Z > p.tower_z1 - 0.6]
            if ce:
                bracket = fillet(ce, r)
            break
        except Exception:
            continue
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
