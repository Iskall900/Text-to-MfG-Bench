"""A15 bracket - iteration 7 geometry.

Stiffened tower:
  * deeper / thicker side columns (8 mm and 7 mm in X, 11 mm in Y)
  * 2 mm shear web joining the columns
  * central rear column under the stage plate
  * pedestal ring at the tower footprint outside the keep-out
  * direct T3-to-tower diagonal strut
  * deep ribs on T1/T2 base arms outside the keep-out
  * 8 mm stage plate (washer seats on the outboard face)
  * two 4.5 x 12 mm diagonal members

Keep-out (documented interpretation):
  vertical cylinder R=70 at (79.4, 19.5), z = 3.31 ... 112.51.
  STEP z -> setup z: z_setup = z_step + 81.11
  (cylinder bottom = top of 3.31 mm base pads; top at lower stage bore plane)
"""
from build123d import *
import json, math, os

# ---------------------------------------------------------------- interfaces
T = {
    "T1": (30.03, -21.45, 0.0),
    "T2": (30.03, 42.047, 0.0),
    "T3": (-58.86, 42.047, 0.0),
}
S = {
    "S1": (11.075, -7.164, 112.51),
    "S2": (-14.32, -7.164, 112.51),
    "S3": (-14.32, -7.164, 137.91),
    "S4": (11.075, -7.164, 137.91),
}
PAYLOAD = (-1.6225, -57.164, 125.21)
KEEP_C = (79.4, 19.5)
KEEP_R = 70.0
KEEP_Z0 = 3.31
KEEP_Z1 = 112.51

T_HOLE_D = 6.6
S_HOLE_D = 6.5
BASE_T = 3.31

# ---------------------------------------------------------------- base plate
hub = Pos(-12.0, 9.5, BASE_T / 2) * Box(44.0, 69.0, BASE_T)

p0 = (-15.0, 32.0)
p1 = (T["T3"][0] - 9.8, T["T3"][1] + 2.25)
L3 = math.dist(p0, p1)
a3 = math.degrees(math.atan2(p1[1] - p0[1], p1[0] - p0[0]))
arm3 = Pos((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, BASE_T / 2) * Rot(Z=a3) * Box(L3, 20.0, BASE_T)
arm1 = Pos(22.5, T["T1"][1], BASE_T / 2) * Box(35.0, 20.0, BASE_T)
arm2 = Pos(22.5, T["T2"][1], BASE_T / 2) * Box(35.0, 20.0, BASE_T)

# pedestal ring under the tower (all x <= 6, outside the keep-out which starts
# at x = 9.4).  It turns the 3.31 mm base plate into a stiff box at the tower
# footprint without entering the keep-out cylinder.
RING_Z0, RING_Z1 = 3.0, 11.31
ring_h = RING_Z1 - RING_Z0
ring_zc = (RING_Z0 + RING_Z1) / 2
ring_parts = [
    Pos(-29.0, 10.5, ring_zc) * Box(4.0, 67.0, ring_h),   # left longitudinal
    Pos(4.0, 10.5, ring_zc) * Box(4.0, 67.0, ring_h),     # right longitudinal
    Pos(-12.5, -21.0, ring_zc) * Box(37.0, 4.0, ring_h),  # front transverse
    Pos(-12.5, 42.0, ring_zc) * Box(37.0, 4.0, ring_h),   # rear transverse
]

base = hub + arm3 + arm1 + arm2
for _p in ring_parts:
    base += _p

# ---------------------------------------------------------------- side frames
X_LEFT = (-31.0, -23.0)   # 8 mm thick
X_RIGHT = (1.5, 8.5)      # 7 mm thick
COL_Y0, COL_Y1 = -19.164, -8.164   # 11 mm deep
COL_Z0, COL_Z1 = 2.0, 104.0
COL_ZC = (COL_Z0 + COL_Z1) / 2

frames = []
for x0, x1 in (X_LEFT, X_RIGHT):
    xc = (x0 + x1) / 2
    frames.append(
        Pos(xc, (COL_Y0 + COL_Y1) / 2, COL_ZC)
        * Box(x1 - x0, COL_Y1 - COL_Y0, COL_Z1 - COL_Z0)
    )

# shear web between columns (2 mm thick, just behind the stage plate front face)
web = Pos(-10.75, -14.0, (2.0 + 103.9) / 2) * Box(24.7, 2.0, 103.9 - 2.0)

# rear central column under the stage plate bolt line
rear_col = Pos(-3.0, -10.75, (2.0 + 104.5) / 2) * Box(12.0, 2.5, 104.5 - 2.0)

# ---------------------------------------------------------------- diagonals
DIAG_P0 = (36.0, 2.0)
DIAG_P1 = (-10.5, 104.5)
DIAG_W = 12.0
DIAG_T = 4.5
DIAG_L = math.dist(DIAG_P0, DIAG_P1)
DIAG_ANG = math.degrees(math.atan2(-(DIAG_P1[0] - DIAG_P0[0]), DIAG_P1[1] - DIAG_P0[1]))
DIAG_MID = ((DIAG_P0[0] + DIAG_P1[0]) / 2, (DIAG_P0[1] + DIAG_P1[1]) / 2)

for x0, x1 in (X_LEFT, X_RIGHT):
    xc = (x0 + x1) / 2
    frames.append(
        Pos(xc, DIAG_MID[0], DIAG_MID[1])
        * Rot(X=DIAG_ANG)
        * Box(DIAG_T, DIAG_W, DIAG_L)
    )

# direct diagonal strut from the T3 bolt region to the left column.
# It is entirely at x < 9.4, hence outside the keep-out cylinder.
strut_start = Vector(-50.0, 36.0, 2.0)
strut_end = Vector(-25.0, -13.0, 75.0)
strut_dir = strut_end - strut_start
strut_len = strut_dir.length
strut = extrude(Plane(origin=strut_start, z_dir=strut_dir) * Rectangle(5.0, 6.0), amount=strut_len)

# short deep ribs on the T1 and T2 base arms.  At these Y stations the
# keep-out cylinder boundary is at x ~= 21.2 (T1) and ~= 11.6 (T2), so the
# ribs can extend well outboard of the pedestal ring without entering it.
t1_rib = Pos(13.4, -21.45, (3.0 + 19.31) / 2) * Box(14.8, 4.0, 16.31)
t2_rib = Pos(8.5, 42.047, (3.0 + 19.31) / 2) * Box(5.0, 4.0, 16.31)

# ---------------------------------------------------------------- stage plate
stage_pts = [(-33.0, -15.164), (18.0, -15.164), (16.0, -7.164), (-31.0, -7.164)]
stage_face = make_face(Polyline(*stage_pts, close=True))
STAGE_Z0, STAGE_Z1 = 104.0, 146.1
stage = extrude(Pos(0, 0, STAGE_Z0) * stage_face, amount=STAGE_Z1 - STAGE_Z0)

# ---------------------------------------------------------------- union
bracket = base + web + stage + strut + t1_rib + t2_rib
for f in frames:
    bracket += f

# ---------------------------------------------------------------- holes
cuts = []
for name, (x, y, z) in T.items():
    cuts.append(Pos(x, y, -1.0) * Cylinder(T_HOLE_D / 2, 8.0, align=(Align.CENTER, Align.CENTER, Align.MIN)))
for name, (x, y, z) in S.items():
    cuts.append(
        Pos(x, -15.6, z) * Rot(X=-90) * Cylinder(S_HOLE_D / 2, 13.6, align=(Align.CENTER, Align.CENTER, Align.MIN))
    )
for c in cuts:
    bracket -= c

# ---------------------------------------------------------------- keep-out
keepout = Pos(KEEP_C[0], KEEP_C[1], KEEP_Z0) * Cylinder(
    KEEP_R, KEEP_Z1 - KEEP_Z0, align=(Align.CENTER, Align.CENTER, Align.MIN)
)
inter_vol = (bracket & keepout).volume if (bracket & keepout) else 0.0
bracket = bracket - keepout

# clip below telescope plane
bracket = bracket & Pos(0, 0, 100) * Box(400, 400, 200)

# ---------------------------------------------------------------- checks
solids = bracket.solids()
vol = bracket.volume
mass = vol * 2.70e-3
bb = bracket.bounding_box()

print(f"solids           : {len(solids)}")
print(f"volume           : {vol:.2f} mm^3")
print(f"mass             : {mass:.2f} g  ({mass/1000:.5f} kg)")
print(f"bbox             : x {bb.min.X:.3f}..{bb.max.X:.3f}  y {bb.min.Y:.3f}..{bb.max.Y:.3f}  z {bb.min.Z:.3f}..{bb.max.Z:.3f}")
print(f"keepout intersect: {inter_vol:.6f} mm^3 (pre-trim)")

for nm, (x, y, z) in {**T, **S}.items():
    rr = T_HOLE_D / 2 if nm.startswith("T") else S_HOLE_D / 2
    found = 0
    for f in bracket.faces():
        if f.geom_type == GeomType.CYLINDER and abs(f.radius - rr) < 0.05:
            ax = f.axis_of_rotation
            v = (x - ax.position.X, y - ax.position.Y, z - ax.position.Z)
            dax = (ax.direction.X, ax.direction.Y, ax.direction.Z)
            along = sum(a * b for a, b in zip(v, dax))
            d = math.sqrt(max(0.0, sum(a * a for a in v) - along * along))
            if d < 1e-3:
                found += 1
    print(f"hole {nm}: cylindrical faces at exact location = {found}")

outdir = os.path.dirname(os.path.abspath(__file__))
export_step(bracket, os.path.join(outdir, "A15_bracket_i7.step"))
export_stl(bracket, os.path.join(outdir, "A15_bracket_i7.stl"), tolerance=0.05, angular_tolerance=0.2)

meta = {
    "iteration": 7,
    "solid_count": len(solids),
    "volume_mm3": vol,
    "mass_g": mass,
    "mass_kg": mass / 1000.0,
    "bbox": {"x": [bb.min.X, bb.max.X], "y": [bb.min.Y, bb.max.Y], "z": [bb.min.Z, bb.max.Z]},
    "keepout": {"center": KEEP_C, "radius": KEEP_R, "z": [KEEP_Z0, KEEP_Z1], "pre_trim_intersection_mm3": inter_vol},
    "interfaces": {"T": T, "S": S, "payload_cg": PAYLOAD},
    "base_thickness_mm": BASE_T,
    "stage_plate_thickness_mm": 8.0,
    "columns": {"left_x": X_LEFT, "right_x": X_RIGHT, "y": [COL_Y0, COL_Y1]},
}
with open(os.path.join(outdir, "A15_bracket_i7_meta.json"), "w") as fh:
    json.dump(meta, fh, indent=2)
print("wrote", outdir)
