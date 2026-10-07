"""Run real geometry checks: .venv/bin/python DfM/verify_dfm.py (no skips)."""
from __future__ import annotations

import copy
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from build123d import Align, Axis, Box, Compound, Cone, Cylinder, Edge, Pos, Rot, Solid, Sphere, Vector, export_step, fillet
from DfM.check_dfm import CHECK_NAMES, check, load_config, write_reports


def config():
    value = load_config(Path(__file__).with_name("config.json"))
    value["sampling"].update(face_u=2, face_v=2, edge_points=3,
                             approach_directions=8, pocket_angles=8)
    value["limits"].update(min_wall_mm=1, min_internal_radius_mm=0.5,
                           max_pocket_depth_width=1, min_hole_diameter_mm=2,
                           max_hole_depth_mm=8)
    value["tools"] = [dict(name="small_flat", kind="flat", diameter_mm=1,
                           cutting_length_mm=12, shank_diameter_mm=1,
                           stickout_mm=20, holder_diameter_mm=3,
                           holder_length_mm=10, holder_clearance_mm=0)]
    return value


def pocket(rounding=0, rotation=False):
    body = Box(20, 20, 12, align=(Align.CENTER, Align.CENTER, Align.MIN))
    cut = Pos(0, 0, 4) * Box(8, 6, 8, align=(Align.CENTER, Align.CENTER, Align.MIN))
    if rounding:
        cut = fillet(cut.edges().filter_by(Axis.Z), rounding)
    part = body - cut
    return Rot(20, 30, 40) * part if rotation else part


def findings(report, name):
    return [row for row in report.violations if row.check_name == name]


class GeometryChecks(unittest.TestCase):
    def test_transitive_stepped_hole_depth(self):
        body = Box(30, 30, 30, align=(Align.CENTER, Align.CENTER, Align.MIN))
        cutter = (Cylinder(1, 4, align=(Align.CENTER, Align.CENTER, Align.MIN))
                  + Pos(0, 0, 4)*Cylinder(2, 6, align=(Align.CENTER, Align.CENTER, Align.MIN))
                  + Pos(0, 0, 10)*Cylinder(3, 20, align=(Align.CENTER, Align.CENTER, Align.MIN)))
        cfg = config()
        cfg["limits"].update(min_hole_diameter_mm=0.1, max_hole_depth_mm=29)
        rows = findings(check(body-cutter, cfg), "MAX_HOLE_DEPTH")
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0].measured_value, 30, places=6)

    def test_compound_cannot_discard_loose_geometry(self):
        for loose in (Edge.make_line((30, 30, 30), (31, 30, 30)),
                      Pos(30, 0, 0)*Box(2, 2, 2).faces()[0]):
            with self.assertRaises(ValueError):
                check(Compound([Box(2, 2, 2), loose]), config())
        self.assertFalse(findings(check(Compound([Compound([Box(10, 10, 10)])]), config()),
                                  "MIN_WALL_THICKNESS"))

    def test_non_cylindrical_through_hole_is_inconclusive(self):
        part = Box(20, 20, 10) - Box(4, 4, 10)
        report = check(part, config())
        for name in ("MIN_HOLE_DIAMETER", "MAX_HOLE_DEPTH"):
            self.assertTrue(any(row.check_name == name for row in report.inconclusive), report.inconclusive)

    def test_kernel_collision_failure_is_inconclusive_not_a_violation(self):
        from unittest.mock import patch
        with patch("DfM.check_dfm.common_volume", side_effect=RuntimeError("simulated native failure")):
            report = check(Box(10, 10, 10), config())
        self.assertFalse(findings(report, "TOOL_ACCESSIBILITY"))
        self.assertEqual(dict(report.coverage)["TOOL_ACCESSIBILITY"], 0)
        self.assertTrue(any(row.check_name == "TOOL_ACCESSIBILITY" for row in report.inconclusive))

    def test_feature_kernel_failure_does_not_abort_other_checks(self):
        from unittest.mock import patch
        part = Box(20, 20, 0.5) - Cylinder(0.5, 0.5)
        with patch("DfM.check_dfm.Geometry.edge_points", side_effect=RuntimeError("simulated native failure")):
            report = check(part, config())
        self.assertTrue(findings(report, "MIN_WALL_THICKNESS"))
        for name in ("MIN_HOLE_DIAMETER", "MAX_HOLE_DEPTH", "POCKET_DEPTH_WIDTH"):
            self.assertTrue(any(row.check_name == name for row in report.inconclusive))

    def test_bore_sampling_density_is_configurable(self):
        cfg = config()
        cfg["sampling"]["hole_axial_samples"] = 5
        part = Box(20, 20, 10) - Cylinder(0.5, 10)
        report = check(part, cfg)
        self.assertEqual(len(findings(report, "MIN_HOLE_DIAMETER")), 1)

    def test_open_curved_cavity_cannot_silently_pass_feature_checks(self):
        body = Box(20, 20, 10, align=(Align.CENTER, Align.CENTER, Align.MIN))
        for part in (body-Pos(0, 0, 10)*Sphere(3),
                     body-Pos(0, 0, 8)*Cone(0, 8, 2, align=(Align.CENTER, Align.CENTER, Align.MIN))):
            report = check(part, config())
            self.assertTrue(any(row.check_name == "POCKET_DEPTH_WIDTH" for row in report.inconclusive))

    def test_zero_length_shank_has_no_collision_volume(self):
        cfg = config()
        cfg["tools"][0].update(cutting_length_mm=2, stickout_mm=2,
                               shank_diameter_mm=100, holder_diameter_mm=1)
        report = check(pocket(), cfg)
        self.assertFalse(findings(report, "TOOL_ACCESSIBILITY"), report.inconclusive)

    def test_countersink_depth_and_unrecognized_taper(self):
        body = Box(20, 20, 10, align=(Align.CENTER, Align.CENTER, Align.MIN))
        through = body - (Cylinder(1, 8, align=(Align.CENTER, Align.CENTER, Align.MIN))
                          + Pos(0, 0, 8)*Cone(1, 3, 2, align=(Align.CENTER, Align.CENTER, Align.MIN)))
        report = check(through, config())
        depths = findings(report, "MAX_HOLE_DEPTH")
        self.assertEqual(len(depths), 1, report.inconclusive)
        self.assertAlmostEqual(depths[0].measured_value, 10, places=6)
        taper = body - Pos(0, 0, 2)*Cone(0, 3, 8, align=(Align.CENTER, Align.CENTER, Align.MIN))
        report = check(taper, config())
        self.assertTrue(any(row.check_name == "MIN_HOLE_DIAMETER" for row in report.inconclusive))

    def test_conical_bottom_and_split_cylinder_faces(self):
        from OCP.BRep import BRep_Tool
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeSolid, BRepBuilderAPI_Sewing
        from OCP.GeomAbs import GeomAbs_Cylinder
        from OCP.TopoDS import TopoDS
        body = Box(20, 20, 10, align=(Align.CENTER, Align.CENTER, Align.MIN))
        cutter = (Pos(0, 0, 4) * Cylinder(1, 6, align=(Align.CENTER, Align.CENTER, Align.MIN))
                  + Pos(0, 0, 2) * Cone(0, 1, 2, align=(Align.CENTER, Align.CENTER, Align.MIN)))
        cfg = config()
        cfg["limits"]["max_hole_depth_mm"] = 7
        rows = findings(check(body-cutter, cfg), "MAX_HOLE_DEPTH")
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0].measured_value, 8, places=6)
        part = body - Cylinder(0.5, 10, align=(Align.CENTER, Align.CENTER, Align.MIN))
        cylinder_face = next(f for f in part.faces() if BRepAdaptor_Surface(f.wrapped).GetType() == GeomAbs_Cylinder)
        surface = BRepAdaptor_Surface(cylinder_face.wrapped)
        u0, u1 = surface.FirstUParameter(), surface.LastUParameter()
        v0, v1 = surface.FirstVParameter(), surface.LastVParameter()
        sewing = BRepBuilderAPI_Sewing(1e-7)
        for face in part.faces():
            if not face.is_same(cylinder_face):
                sewing.Add(face.wrapped)
        for low, high in ((u0, (u0+u1)/2), ((u0+u1)/2, u1)):
            face = BRepBuilderAPI_MakeFace(BRep_Tool.Surface_s(cylinder_face.wrapped), low, high, v0, v1, 1e-7).Face()
            face.Orientation(cylinder_face.wrapped.Orientation())
            sewing.Add(face)
        sewing.Perform()
        split = Solid(BRepBuilderAPI_MakeSolid(TopoDS.Shell(sewing.SewedShape())).Solid())
        self.assertTrue(split.is_valid)
        report = check(split, config())
        self.assertEqual(len(findings(report, "MIN_HOLE_DIAMETER")), 1, report.inconclusive)
        self.assertEqual(len(findings(report, "MAX_HOLE_DEPTH")), 1, report.inconclusive)

        # Repeat with axial face splits deliberately ordered high, low, bridge.
        sewing = BRepBuilderAPI_Sewing(1e-7)
        for face in part.faces():
            if not face.is_same(cylinder_face):
                sewing.Add(face.wrapped)
        for low, high in ((v0+5, v1), (v0, v0+2), (v0+2, v0+5)):
            face = BRepBuilderAPI_MakeFace(BRep_Tool.Surface_s(cylinder_face.wrapped), u0, u1, low, high, 1e-7).Face()
            face.Orientation(cylinder_face.wrapped.Orientation())
            sewing.Add(face)
        sewing.Perform()
        split = Solid(BRepBuilderAPI_MakeSolid(TopoDS.Shell(sewing.SewedShape())).Solid())
        report = check(split, config())
        self.assertEqual(len(findings(report, "MIN_HOLE_DIAMETER")), 1, report.inconclusive)
        self.assertEqual(len(findings(report, "MAX_HOLE_DEPTH")), 1, report.inconclusive)
        self.assertAlmostEqual(findings(report, "MAX_HOLE_DEPTH")[0].measured_value, 10, places=6)

    def test_other_limits_and_surface_coordinates(self):
        cfg = config()
        cfg["limits"]["max_pocket_depth_width"] = 8/6
        self.assertFalse(findings(check(pocket(), cfg), "POCKET_DEPTH_WIDTH"))
        part = Box(20, 20, 10) - Cylinder(0.5, 10)
        cfg["limits"].update(min_hole_diameter_mm=1, max_hole_depth_mm=10)
        report = check(part, cfg)
        self.assertFalse(findings(report, "MIN_HOLE_DIAMETER"))
        self.assertFalse(findings(report, "MAX_HOLE_DEPTH"))
        cfg["limits"]["min_accessible_directions"] = 1000
        rows = findings(check(Box(10, 10, 10), cfg), "TOOL_ACCESSIBILITY")
        self.assertEqual(len(rows), 24)
        self.assertTrue(all(row.measured_value < row.limit for row in rows))
        part = pocket()
        for row in check(part, config()).violations:
            face = part.faces()[row.face_id-1]
            self.assertLess(face.distance_to(Vector(row.x, row.y, row.z)), 1e-6)

    def test_thin_wall_and_configurable_threshold(self):
        part = Box(10, 10, 0.5)
        cfg = config()
        rows = findings(check(part, cfg), "MIN_WALL_THICKNESS")
        self.assertTrue(rows)
        self.assertTrue(any(abs(row.measured_value - 0.5) < 1e-6 for row in rows))
        cfg["limits"]["min_wall_mm"] = 0.5
        self.assertFalse(findings(check(part, cfg), "MIN_WALL_THICKNESS"))
        cfg["limits"]["min_wall_mm"] = 0.5 + cfg["tolerances"]["linear_mm"] / 2
        self.assertFalse(findings(check(part, cfg), "MIN_WALL_THICKNESS"))

    def test_pockets_corners_and_rotated_measurements(self):
        for rotated in (False, True):
            report = check(pocket(rotation=rotated), config())
            self.assertFalse([r for r in report.inconclusive if r.check_name in
                              ("INTERNAL_CORNER_RADIUS", "POCKET_DEPTH_WIDTH")])
            rows = findings(report, "POCKET_DEPTH_WIDTH")
            self.assertTrue(rows, report.inconclusive)
            self.assertAlmostEqual(rows[0].measured_value, 8 / 6, places=5)
            corners = findings(report, "INTERNAL_CORNER_RADIUS")
            self.assertTrue(corners, report.inconclusive)
            self.assertTrue(all(row.measured_value == 0 for row in corners))
        cfg = config()
        cfg["limits"]["min_internal_radius_mm"] = 1.1
        report = check(pocket(rounding=1), cfg)
        corners = findings(report, "INTERNAL_CORNER_RADIUS")
        self.assertTrue(corners, report.inconclusive)
        self.assertTrue(all(abs(row.measured_value - 1) < 1e-5 for row in corners))
        cfg["limits"]["min_internal_radius_mm"] = 1
        self.assertFalse(findings(check(pocket(rounding=1), cfg), "INTERNAL_CORNER_RADIUS"))

    def test_holes_bosses_blind_through_and_stepped(self):
        body = Box(20, 20, 10, align=(Align.CENTER, Align.CENTER, Align.MIN))
        through = body - Cylinder(0.5, 10, align=(Align.CENTER, Align.CENTER, Align.MIN))
        for part in (through, Rot(25, 35, 15) * through):
            report = check(part, config())
            sizes = findings(report, "MIN_HOLE_DIAMETER")
            depths = findings(report, "MAX_HOLE_DEPTH")
            self.assertEqual(len(sizes), 1, report.inconclusive)
            self.assertEqual(len(depths), 1, report.inconclusive)
            self.assertAlmostEqual(sizes[0].measured_value, 1, places=6)
            self.assertAlmostEqual(depths[0].measured_value, 10, places=5)
            self.assertFalse(findings(report, "INTERNAL_CORNER_RADIUS"))
        blind = body - Pos(0, 0, 4) * Cylinder(0.5, 6, align=(Align.CENTER, Align.CENTER, Align.MIN))
        self.assertFalse(findings(check(blind, config()), "MAX_HOLE_DEPTH"))
        stepped = through - Pos(0, 0, 7) * Cylinder(3, 3, align=(Align.CENTER, Align.CENTER, Align.MIN))
        report = check(stepped, config())
        self.assertEqual(len(findings(report, "MAX_HOLE_DEPTH")), 1, report.inconclusive)
        self.assertAlmostEqual(findings(report, "MAX_HOLE_DEPTH")[0].measured_value, 10, places=5)
        self.assertFalse(findings(check(Cylinder(0.5, 10), config()), "MIN_HOLE_DIAMETER"))

    def test_accessible_side_faces_ball_contact_and_holder_collision(self):
        cfg = config()
        report = check(Box(10, 10, 10), cfg)
        self.assertFalse(findings(report, "TOOL_ACCESSIBILITY"), report.inconclusive)
        self.assertFalse([r for r in report.inconclusive if r.check_name == "TOOL_ACCESSIBILITY"])
        cfg["tools"][0]["kind"] = "ball"
        self.assertFalse(findings(check(Sphere(5), cfg), "TOOL_ACCESSIBILITY"))
        cfg = config()
        cfg["tools"][0].update(stickout_mm=2, cutting_length_mm=2,
                               holder_diameter_mm=12)
        report = check(pocket(), cfg)
        self.assertTrue(findings(report, "TOOL_ACCESSIBILITY"), report.inconclusive)
        cfg["tools"][0].update(stickout_mm=20, cutting_length_mm=12)
        self.assertFalse(findings(check(pocket(), cfg), "TOOL_ACCESSIBILITY"))

    def test_enclosed_cavity_and_unsupported_pocket_are_not_green(self):
        sealed = Box(20, 20, 20) - Sphere(3)
        report = check(sealed, config())
        self.assertTrue(findings(report, "TOOL_ACCESSIBILITY"), report.inconclusive)
        body = Box(20, 20, 12, align=(Align.CENTER, Align.CENTER, Align.MIN))
        open_slot = body - Pos(0, 0, 4) * Box(25, 6, 8, align=(Align.CENTER, Align.CENTER, Align.MIN))
        report = check(open_slot, config())
        self.assertTrue(any(r.check_name == "POCKET_DEPTH_WIDTH" for r in report.inconclusive))

    def test_invalid_inputs_and_configs(self):
        for part in (Compound(), Compound(children=[Box(2, 2, 2), Pos(10, 0, 0) * Box(2, 2, 2)]),
                     Box(2, 2, 2).faces()[0], object()):
            with self.assertRaises((ValueError, TypeError)):
                check(part, config())
        for field, value in (("min_wall_mm", -1), ("max_hole_depth_mm", float("nan")),
                             ("min_accessible_directions", 0)):
            cfg = config()
            cfg["limits"][field] = value
            with self.assertRaises(ValueError):
                check(Box(2, 2, 2), cfg)
        cfg = config()
        cfg["tools"][0]["stickout_mm"] = 1
        with self.assertRaises(ValueError):
            check(Box(2, 2, 2), cfg)

    def test_reports_input_preservation_and_repeatability(self):
        part = pocket()
        volume = part.volume
        faces = len(part.faces())
        cfg = config()
        original = copy.deepcopy(cfg)
        report = check(part, cfg)
        self.assertEqual(cfg, original)
        self.assertAlmostEqual(part.volume, volume, places=10)
        self.assertEqual(len(part.faces()), faces)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_reports(report, root / "first")
            write_reports(check(part, cfg), root / "second")
            for name in ("report.txt", "violations.csv"):
                self.assertEqual((root / "first" / name).read_bytes(),
                                 (root / "second" / name).read_bytes())
            with (root / "first" / "violations.csv").open(encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), len(report.violations))
            self.assertEqual(list(rows[0]), ["check_name", "x", "y", "z", "face_id",
                                            "measured_value", "limit", "explanation"])
            text = (root / "first" / "report.txt").read_text()
            for name in CHECK_NAMES:
                self.assertIn(f"{name}: {len(findings(report, name))}", text)
            step = root / "fixture.step"
            export_step(part, step)
            config_file = root / "config.json"
            config_file.write_text(json.dumps(cfg))
            for index, seed in enumerate(("1", "777")):
                run = subprocess.run([sys.executable, str(Path(__file__).with_name("check_dfm.py")),
                                      str(step), "--config", str(config_file),
                                      "--output-dir", str(root / f"process{index}")],
                                     env={**os.environ, "PYTHONHASHSEED": seed},
                                     capture_output=True, text=True)
                self.assertEqual(run.returncode, 1, run.stderr)
            for name in ("report.txt", "violations.csv"):
                self.assertEqual((root / "process0" / name).read_bytes(),
                                 (root / "process1" / name).read_bytes())


if __name__ == "__main__":
    unittest.main(verbosity=2)
